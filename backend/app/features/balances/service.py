from __future__ import annotations

from datetime import date
from math import ceil, isclose, isfinite
from typing import Any

from fastapi import HTTPException, status

from ...core.database import utc_now_iso
from . import repository

EPSILON = 1e-7


def overview(
    conn,
    *,
    workspace_id: int,
    page: int = 1,
    page_size: int = 5,
    topup_page: int = 1,
    topup_page_size: int = 5,
) -> dict[str, Any]:
    def history_page(requested_page, requested_size, *, topups):
        count = repository.history_count(conn, workspace_id, topups=topups)
        size = max(1, min(int(requested_size), 100))
        pages = max(1, ceil(count / size))
        selected = max(1, min(int(requested_page), pages))
        return repository.list_history(conn, workspace_id, page=selected, page_size=size, topups=topups), {
            "page": selected, "page_size": size, "total_items": count, "total_pages": pages,
        }

    history, pagination = history_page(page, page_size, topups=False)
    additions, additions_pagination = history_page(topup_page, topup_page_size, topups=True)
    return {
        "providers": repository.list_providers(conn),
        "latest": repository.latest_entry(conn, workspace_id),
        "summary": repository.usage_summary(conn, workspace_id),
        "history": history, "pagination": pagination,
        "topup_history": additions, "topup_pagination": additions_pagination,
    }


def get_history_entry(conn, entry_id: int, workspace_id: int) -> dict[str, Any]:
    entry = repository.get_history_entry(conn, entry_id, workspace_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History entry not found.")
    return entry


def history_count(conn, workspace_id: int) -> int:
    return repository.history_count(conn, workspace_id)


def latest_entry(conn, workspace_id: int) -> dict[str, Any] | None:
    return repository.latest_entry(conn, workspace_id)


def _as_number(value, field_name: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"{field_name} must be a number.") from exc
    if not isfinite(number):
        raise HTTPException(status_code=422, detail=f"{field_name} must be a finite number.")
    if number < 0:
        raise HTTPException(status_code=422, detail=f"{field_name} cannot be negative.")
    return max(0.0, number)


def _calculate_value(
    *,
    provider_name: str,
    total,
    used,
    left,
    default_total: float,
) -> tuple[float, float, float]:
    total_n = _as_number(total, f"{provider_name} total")
    used_n = _as_number(used, f"{provider_name} used")
    left_n = _as_number(left, f"{provider_name} left")
    if total_n is None:
        total_n = used_n + left_n if used_n is not None and left_n is not None else float(default_total)
    if not isfinite(total_n):
        raise HTTPException(status_code=422, detail=f"{provider_name}: Total must be a finite number.")
    if used_n is None and left_n is None:
        used_n, left_n = 0.0, total_n
    elif used_n is None:
        used_n = total_n - left_n
    elif left_n is None:
        left_n = total_n - used_n
    elif not isclose(used_n + left_n, total_n, abs_tol=1e-8):
        raise HTTPException(
            status_code=422,
            detail=f"{provider_name}: Used + Left must equal Total. Edit either Used or Left so the values match.",
        )
    if used_n < -EPSILON or left_n < -EPSILON:
        raise HTTPException(status_code=422, detail=f"{provider_name}: Used or Left cannot be greater than Total.")
    if not all(isfinite(value) for value in (total_n, used_n, left_n)):
        raise HTTPException(status_code=422, detail=f"{provider_name}: Balances must be finite numbers.")
    return round(total_n, 12), round(max(0.0, used_n), 12), round(max(0.0, left_n), 12)


def create_history_entry(
    conn,
    user_id: int,
    payload: dict[str, Any],
    *,
    workspace_id: int,
) -> dict[str, Any]:
    conn.execute("BEGIN IMMEDIATE")
    providers = repository.list_providers(conn)
    latest = repository.latest_entry(conn, workspace_id)
    expected_latest_entry_id = payload.get("expected_latest_entry_id")
    latest_entry_id = latest["id"] if latest else None
    if expected_latest_entry_id != latest_entry_id:
        raise HTTPException(
            status_code=409,
            detail="Balances changed since this form was opened. Refresh and try again.",
        )
    latest_map = {value["provider_key"]: value for value in (latest["values"] if latest else [])}
    incoming = payload.get("values") or {}
    entry_date = str(payload.get("entry_date") or date.today().isoformat())
    now = utc_now_iso()
    entry_id = repository.insert_history_entry(
        conn,
        entry_date=entry_date,
        created_at=now,
        user_id=user_id,
        workspace_id=workspace_id,
    )
    for provider in providers:
        supplied = incoming.get(provider["provider_key"]) or {}
        default_total = float(latest_map.get(provider["provider_key"], {}).get("left_balance", 0.0))
        total, used, left = _calculate_value(
            provider_name=provider["display_name"],
            total=supplied.get("total"),
            used=supplied.get("used"),
            left=supplied.get("left"),
            default_total=default_total,
        )
        repository.insert_value(
            conn,
            entry_id=entry_id,
            provider_id=int(provider["id"]),
            total=total,
            used=used,
            left=left,
        )
    return get_history_entry(conn, entry_id, workspace_id)


def create_add_balance_entry(
    conn,
    user_id: int,
    payload: dict[str, Any],
    *,
    workspace_id: int,
) -> dict[str, Any]:
    """Apply top-ups to the latest authorized workspace snapshot."""
    conn.execute("BEGIN IMMEDIATE")
    providers = repository.list_providers(conn)
    latest = repository.latest_entry(conn, workspace_id)
    latest_map = {value["provider_key"]: value for value in (latest["values"] if latest else [])}
    additions = payload.get("additions") or {}
    if set(additions) - {p["provider_key"] for p in providers}:
        raise HTTPException(status_code=422, detail="Unknown API provider in additions.")
    entry_date = str(payload.get("entry_date") or date.today().isoformat())
    normalized_additions: dict[str, float] = {}
    any_positive = False
    for provider in providers:
        amount = _as_number(additions.get(provider["provider_key"]), f"{provider['display_name']} added balance")
        amount = 0.0 if amount is None else amount
        normalized_additions[provider["provider_key"]] = amount
        any_positive = any_positive or amount > 0
    if not any_positive:
        raise HTTPException(status_code=422, detail="Enter an amount greater than 0 for at least one API key.")

    now = utc_now_iso()
    entry_id = repository.insert_history_entry(
        conn,
        entry_date=entry_date,
        created_at=now,
        user_id=user_id,
        workspace_id=workspace_id,
        entry_kind="topup",
    )
    for provider in providers:
        previous_left = float(latest_map.get(provider["provider_key"], {}).get("left_balance", 0.0))
        new_total = round(previous_left + normalized_additions[provider["provider_key"]], 12)
        if not isfinite(new_total):
            raise HTTPException(
                status_code=422,
                detail=f"{provider['display_name']}: Added balance exceeds the supported range.",
            )
        repository.insert_value(
            conn,
            entry_id=entry_id,
            provider_id=int(provider["id"]),
            total=new_total,
            used=0.0,
            left=new_total,
            added_balance=normalized_additions[provider["provider_key"]],
            balance_before=previous_left,
        )
    return get_history_entry(conn, entry_id, workspace_id)


def update_history_entry(
    conn,
    entry_id: int,
    user_id: int,
    payload: dict[str, Any],
    *,
    workspace_id: int,
) -> dict[str, Any]:
    conn.execute("BEGIN IMMEDIATE")
    existing = get_history_entry(conn, entry_id, workspace_id)
    if existing["entry_kind"] == "topup":
        raise HTTPException(status_code=409, detail="Use the added balance editor to correct this top-up.")
    providers = repository.list_providers(conn)
    existing_map = {value["provider_key"]: value for value in existing["values"]}
    incoming = payload.get("values") or {}
    entry_date = str(payload.get("entry_date") or existing["entry_date"])
    repository.update_entry_metadata(
        conn,
        entry_id=entry_id,
        workspace_id=workspace_id,
        entry_date=entry_date,
        updated_at=utc_now_iso(),
        user_id=user_id,
    )
    for provider in providers:
        supplied = incoming.get(provider["provider_key"])
        if supplied is None:
            continue
        old = existing_map.get(provider["provider_key"], {"total_balance": 0})
        total, used, left = _calculate_value(
            provider_name=provider["display_name"],
            total=supplied.get("total"),
            used=supplied.get("used"),
            left=supplied.get("left"),
            default_total=float(old["total_balance"]),
        )
        save_value = repository.update_value if provider["provider_key"] in existing_map else repository.insert_value
        save_value(
            conn,
            entry_id=entry_id,
            provider_id=int(provider["id"]),
            total=total,
            used=used,
            left=left,
        )
    return get_history_entry(conn, entry_id, workspace_id)


def delete_history_entry(conn, entry_id: int, workspace_id: int) -> None:
    if not repository.delete_history_entry(conn, entry_id, workspace_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History entry not found.")


def update_add_balance_entry(conn, entry_id: int, user_id: int, payload: dict[str, Any], *, workspace_id: int) -> dict[str, Any]:
    """Correct a recorded addition, or explicitly classify an unknown legacy snapshot."""
    conn.execute("BEGIN IMMEDIATE")
    existing = get_history_entry(conn, entry_id, workspace_id)
    if existing["entry_kind"] not in {"legacy", "topup"}:
        raise HTTPException(status_code=409, detail="Only legacy entries can be classified as top-ups.")
    additions = payload.get("additions") or {}
    values = {v["provider_key"]: v for v in existing["values"]}
    if set(additions) - set(values):
        raise HTTPException(status_code=422, detail="Unknown API provider in additions.")
    normalized = {key: _as_number(additions.get(key, 0), f"{value['display_name']} added balance") or 0.0
                  for key, value in values.items()}
    if not any(amount > 0 for amount in normalized.values()):
        raise HTTPException(status_code=422, detail="Enter an amount greater than 0 for at least one API key.")
    provider_ids = {p["provider_key"]: p["id"] for p in repository.list_providers(conn)}
    changes = []
    for key, value in values.items():
        added = normalized[key]
        if existing["entry_kind"] == "legacy":
            if value["used_balance"] != 0 or not isclose(value["total_balance"], value["left_balance"], rel_tol=0, abs_tol=1e-8):
                raise HTTPException(status_code=422, detail="A legacy top-up must have zero usage and matching Total and Left balances.")
            before = round(value["left_balance"] - added, 12)
            if before < 0:
                raise HTTPException(status_code=422, detail=f"{value['display_name']}: Added balance cannot exceed the saved balance.")
            after = value["left_balance"]
        else:
            before = value["balance_before"]
            after = round(before + added, 12)
            if not isfinite(after):
                raise HTTPException(status_code=422, detail=f"{value['display_name']}: Added balance exceeds the supported range.")
        changes.append((key, before, added, after))
    repository.update_entry_metadata(conn, entry_id=entry_id, workspace_id=workspace_id,
        entry_date=str(payload.get("entry_date") or existing["entry_date"]), updated_at=utc_now_iso(), user_id=user_id)
    conn.execute("UPDATE history_entries SET entry_kind = 'topup' WHERE id = ? AND workspace_id = ?", (entry_id, workspace_id))
    for key, before, added, after in changes:
        repository.update_value(conn, entry_id=entry_id, provider_id=provider_ids[key], total=after, used=0,
            left=after, added_balance=added, balance_before=before)
    return get_history_entry(conn, entry_id, workspace_id)
