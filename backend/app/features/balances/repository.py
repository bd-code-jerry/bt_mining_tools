from __future__ import annotations

import sqlite3
from typing import Any


def list_providers(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, provider_key, display_name, unit, sort_order FROM providers ORDER BY sort_order"
    ).fetchall()
    return [dict(row) for row in rows]


def history_count(conn: sqlite3.Connection, workspace_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM history_entries WHERE workspace_id = ?",
        (workspace_id,),
    ).fetchone()
    return int(row["c"] if row else 0)


def list_history(
    conn: sqlite3.Connection,
    workspace_id: int,
    *,
    page: int,
    page_size: int,
) -> list[dict[str, Any]]:
    offset = (page - 1) * page_size
    rows = conn.execute(
        """SELECT id, entry_date, created_at, updated_at FROM history_entries
           WHERE workspace_id = ?
           ORDER BY entry_date DESC, id DESC
           LIMIT ? OFFSET ?""",
        (workspace_id, page_size, offset),
    ).fetchall()
    return [_entry_to_dict(conn, row) for row in rows]


def latest_entry(conn: sqlite3.Connection, workspace_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """SELECT id, entry_date, created_at, updated_at FROM history_entries
           WHERE workspace_id = ?
           ORDER BY entry_date DESC, id DESC
           LIMIT 1""",
        (workspace_id,),
    ).fetchone()
    return _entry_to_dict(conn, row) if row else None


def get_history_entry(
    conn: sqlite3.Connection,
    entry_id: int,
    workspace_id: int,
) -> dict[str, Any] | None:
    row = conn.execute(
        """SELECT id, entry_date, created_at, updated_at FROM history_entries
           WHERE id = ? AND workspace_id = ?""",
        (entry_id, workspace_id),
    ).fetchone()
    if not row:
        return None
    return _entry_to_dict(conn, row)


def _entry_to_dict(conn: sqlite3.Connection, entry_row: sqlite3.Row) -> dict[str, Any]:
    values = conn.execute(
        """SELECT p.provider_key, p.display_name, p.unit, p.sort_order,
                  hv.total_balance, hv.used_balance, hv.left_balance
           FROM history_values hv JOIN providers p ON p.id = hv.provider_id
           WHERE hv.entry_id = ? ORDER BY p.sort_order""",
        (entry_row["id"],),
    ).fetchall()
    return {
        "id": int(entry_row["id"]),
        "entry_date": entry_row["entry_date"],
        "created_at": entry_row["created_at"],
        "updated_at": entry_row["updated_at"],
        "values": [dict(row) for row in values],
    }


def usage_summary(conn: sqlite3.Connection, workspace_id: int) -> dict[str, Any]:
    by_provider_rows = conn.execute(
        """SELECT p.provider_key, p.display_name, p.unit, p.sort_order,
                  COALESCE(SUM(hv.used_balance), 0) AS total_used
           FROM providers p
           LEFT JOIN history_entries he ON he.workspace_id = ?
           LEFT JOIN history_values hv ON hv.entry_id = he.id AND hv.provider_id = p.id
           GROUP BY p.id ORDER BY p.sort_order""",
        (workspace_id,),
    ).fetchall()
    by_provider = [dict(row) for row in by_provider_rows]
    by_unit: dict[str, float] = {}
    for row in by_provider:
        unit = row["unit"]
        by_unit[unit] = by_unit.get(unit, 0.0) + float(row["total_used"] or 0.0)
    return {"by_unit": by_unit, "by_provider": by_provider}


def insert_history_entry(
    conn: sqlite3.Connection,
    *,
    entry_date: str,
    created_at: str,
    user_id: int,
    workspace_id: int,
) -> int:
    cursor = conn.execute(
        """INSERT INTO history_entries(entry_date, created_at, updated_at, created_by, updated_by, workspace_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (entry_date, created_at, created_at, user_id, user_id, workspace_id),
    )
    return int(cursor.lastrowid)


def insert_value(
    conn: sqlite3.Connection,
    *,
    entry_id: int,
    provider_id: int,
    total: float,
    used: float,
    left: float,
) -> None:
    conn.execute(
        """INSERT INTO history_values(entry_id, provider_id, total_balance, used_balance, left_balance)
           VALUES (?, ?, ?, ?, ?)""",
        (entry_id, provider_id, total, used, left),
    )


def update_value(
    conn: sqlite3.Connection,
    *,
    entry_id: int,
    provider_id: int,
    total: float,
    used: float,
    left: float,
) -> None:
    conn.execute(
        """UPDATE history_values SET total_balance = ?, used_balance = ?, left_balance = ?
           WHERE entry_id = ? AND provider_id = ?""",
        (total, used, left, entry_id, provider_id),
    )


def update_entry_metadata(
    conn: sqlite3.Connection,
    *,
    entry_id: int,
    workspace_id: int,
    entry_date: str,
    updated_at: str,
    user_id: int,
) -> None:
    conn.execute(
        """UPDATE history_entries SET entry_date = ?, updated_at = ?, updated_by = ?
           WHERE id = ? AND workspace_id = ?""",
        (entry_date, updated_at, user_id, entry_id, workspace_id),
    )


def delete_history_entry(conn: sqlite3.Connection, entry_id: int, workspace_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM history_entries WHERE id = ? AND workspace_id = ?",
        (entry_id, workspace_id),
    )
    return cursor.rowcount > 0
