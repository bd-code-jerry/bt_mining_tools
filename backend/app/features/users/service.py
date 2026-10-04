from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException

from ...core.security import hash_password, unix_now, utc_now_iso, validate_email, validate_password, validate_username
from ..preferences.service import (
    local_date_utc_bounds,
    optional_local_date_utc_bounds,
    to_local_timestamp,
    zone_for,
)
from ..workspaces.repository import ensure_private_workspace
from . import repository

ROLES = frozenset({"admin", "member", "user"})


def _require_user(conn: sqlite3.Connection, user_id: int) -> dict:
    user = repository.get_user(conn, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    return user


def _safe_user(row: dict, viewer_timezone: str) -> dict:
    output = dict(row)
    output["created_at"] = to_local_timestamp(output.get("created_at"), viewer_timezone)
    output["last_login_at"] = to_local_timestamp(output.get("last_login_at"), viewer_timezone)
    output.pop("password_hash", None)
    return output


def present_account(row: dict, viewer_timezone: str) -> dict:
    return _safe_user(row, viewer_timezone)


def list_accounts(conn: sqlite3.Connection, viewer_timezone: str, status_filter: str | None = None) -> list[dict]:
    return [_safe_user(row, viewer_timezone) for row in repository.list_users(conn, status_filter)]


def create_account(
    conn: sqlite3.Connection,
    *,
    username: str,
    email: str,
    password: str,
    role: str,
) -> dict:
    try:
        normalized_username = validate_username(username)
        normalized_email = validate_email(email)
        validate_password(password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if role not in ROLES:
        raise HTTPException(status_code=422, detail="Choose admin, member, or user.")
    encoded_password = hash_password(password)
    conn.execute("BEGIN IMMEDIATE")
    if repository.identifier_in_use(conn, normalized_username, normalized_email):
        raise HTTPException(status_code=409, detail="That username or email address is already in use.")
    try:
        user_id = repository.insert_user(
            conn,
            username=normalized_username,
            email=normalized_email,
            password_hash=encoded_password,
            created_at=utc_now_iso(),
            role=role,
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="That username or email address is already in use.") from exc
    if role == "user":
        ensure_private_workspace(conn, user_id)
    return repository.get_user(conn, user_id)


def approve_pending(conn: sqlite3.Connection, user_id: int, role: str) -> dict:
    if role not in ROLES:
        raise HTTPException(status_code=422, detail="Choose admin, member, or user.")
    conn.execute("BEGIN IMMEDIATE")
    pending = conn.execute("SELECT id FROM users WHERE id = ? AND status = 'pending'", (user_id,)).fetchone()
    if pending is None:
        raise HTTPException(status_code=404, detail="Pending account not found.")
    conn.execute("UPDATE users SET status = 'active', role = ? WHERE id = ?", (role, user_id))
    if role == "user":
        ensure_private_workspace(conn, user_id)
    return repository.get_user(conn, user_id)


def deny_pending(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("BEGIN IMMEDIATE")
    cursor = conn.execute("DELETE FROM users WHERE id = ? AND status = 'pending'", (user_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Pending account not found.")


def change_role(conn: sqlite3.Connection, user_id: int, role: str) -> dict:
    if role not in ROLES:
        raise HTTPException(status_code=422, detail="Choose admin, member, or user.")
    conn.execute("BEGIN IMMEDIATE")
    user = _require_user(conn, user_id)
    if user["status"] != "active":
        raise HTTPException(status_code=409, detail="Only active accounts can change roles.")
    if user["role"] == "admin" and role != "admin" and repository.active_admin_count(conn) <= 1:
        raise HTTPException(status_code=409, detail="The last active administrator cannot be demoted.")
    repository.set_role(conn, user_id, role)
    if role == "user":
        ensure_private_workspace(conn, user_id)
    return repository.get_user(conn, user_id)


def change_status(conn: sqlite3.Connection, user_id: int, account_status: str) -> dict:
    if account_status not in {"active", "disabled"}:
        raise HTTPException(status_code=422, detail="Status must be active or disabled.")
    conn.execute("BEGIN IMMEDIATE")
    user = _require_user(conn, user_id)
    if user["status"] == "pending":
        raise HTTPException(status_code=409, detail="Approve or deny the pending account first.")
    if user["status"] == "active" and account_status == "disabled" and user["role"] == "admin":
        if repository.active_admin_count(conn) <= 1:
            raise HTTPException(status_code=409, detail="The last active administrator cannot be disabled.")
    repository.set_status(conn, user_id, account_status)
    if account_status == "disabled":
        repository.revoke_user_sessions(conn, user_id)
    return repository.get_user(conn, user_id)


def reset_password(conn: sqlite3.Connection, user_id: int, new_password: str) -> None:
    try:
        validate_password(new_password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    conn.execute("BEGIN IMMEDIATE")
    _require_user(conn, user_id)
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_password), user_id))
    repository.revoke_user_sessions(conn, user_id)


def delete_account(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("BEGIN IMMEDIATE")
    user = _require_user(conn, user_id)
    if user["status"] == "active" and user["role"] == "admin" and repository.active_admin_count(conn) <= 1:
        raise HTTPException(status_code=409, detail="The last active administrator cannot be deleted.")
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def update_email(conn: sqlite3.Connection, user_id: int, email: str | None) -> dict:
    normalized = None
    if email is not None and email.strip():
        try:
            normalized = validate_email(email)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    conn.execute("BEGIN IMMEDIATE")
    _require_user(conn, user_id)
    if normalized is not None and conn.execute(
        "SELECT 1 FROM users WHERE id <> ? AND email = ? COLLATE NOCASE", (user_id, normalized)
    ).fetchone():
        raise HTTPException(status_code=409, detail="That email address is already in use.")
    try:
        repository.set_email(conn, user_id, normalized)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="That email address is already in use.") from exc
    return repository.get_user(conn, user_id)


def set_registration(conn: sqlite3.Connection, enabled: bool) -> bool:
    conn.execute("BEGIN IMMEDIATE")
    repository.set_registration_enabled(conn, enabled)
    return enabled


def registration_state(conn: sqlite3.Connection) -> bool:
    return repository.registration_enabled(conn)


def active_sessions(conn: sqlite3.Connection, user_id: int, viewer_timezone: str) -> list[dict]:
    _require_user(conn, user_id)
    sessions = repository.list_sessions(conn, user_id, unix_now())
    output = []
    for session in sessions:
        session["created_at"] = to_local_timestamp(session["created_at"], viewer_timezone)
        session["last_activity_at"] = to_local_timestamp(session["last_activity_at"], viewer_timezone)
        session["expires_at"] = datetime.fromtimestamp(int(session["expires_at"]), timezone.utc).astimezone(
            zone_for(viewer_timezone)
        ).isoformat(timespec="seconds")
        output.append(session)
    return output


def revoke_sessions(conn: sqlite3.Connection, user_id: int) -> int:
    conn.execute("BEGIN IMMEDIATE")
    _require_user(conn, user_id)
    return repository.revoke_user_sessions(conn, user_id)


def revoke_session(conn: sqlite3.Connection, session_id: int) -> None:
    conn.execute("BEGIN IMMEDIATE")
    if not repository.delete_session(conn, session_id):
        raise HTTPException(status_code=404, detail="Session not found.")


def _filter_utc_bounds(
    start_date: date | None,
    end_date: date | None,
    timezone_name: str,
) -> tuple[str | None, str | None]:
    start, end = _effective_login_date_range(start_date, end_date, timezone_name)
    return optional_local_date_utc_bounds(start, end, timezone_name)


def _effective_login_date_range(
    start_date: date | None,
    end_date: date | None,
    timezone_name: str,
) -> tuple[date | None, date | None]:
    if start_date is None and end_date is None:
        return None, None

    today = datetime.now(zone_for(timezone_name)).date()
    start = start_date if start_date is not None else end_date - timedelta(days=29)
    end = end_date if end_date is not None else today
    if end < start:
        raise HTTPException(status_code=422, detail="End date must be on or after start date.")
    if (end - start).days > 366:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 367 days.")
    return start, end


def login_events(
    conn: sqlite3.Connection,
    *,
    viewer_timezone: str,
    start_date: date | None = None,
    end_date: date | None = None,
    account_id: int | None = None,
    role: str | None = None,
) -> list[dict]:
    lower, upper = _filter_utc_bounds(start_date, end_date, viewer_timezone)
    rows = repository.fetch_login_events(
        conn,
        lower_utc=lower,
        upper_utc=upper,
        account_id=account_id,
        role=role,
    )
    for row in rows:
        row["signed_in_at"] = to_local_timestamp(row["signed_in_at"], viewer_timezone)
    return rows


def daily_login_counts(
    conn: sqlite3.Connection,
    *,
    viewer_timezone: str,
    start_date: date | None = None,
    end_date: date | None = None,
    account_id: int | None = None,
    role: str | None = None,
) -> list[dict]:
    zone = zone_for(viewer_timezone)
    today = datetime.now(zone).date()
    start, end = _effective_login_date_range(start_date, end_date, viewer_timezone)
    if start is None or end is None:
        end = today
        start = end - timedelta(days=29)
    lower, upper = local_date_utc_bounds(start, end, viewer_timezone)
    timestamps = repository.fetch_login_timestamps(
        conn,
        lower_utc=lower,
        upper_utc=upper,
        account_id=account_id,
        role=role,
    )
    counts: dict[date, int] = {}
    for stamp in timestamps:
        normalized = stamp[:-1] + "+00:00" if stamp.endswith("Z") else stamp
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        local_day = parsed.astimezone(zone).date()
        counts[local_day] = counts.get(local_day, 0) + 1
    output = []
    current = start
    while current <= end:
        output.append({"date": current.isoformat(), "count": counts.get(current, 0)})
        current += timedelta(days=1)
    return output
