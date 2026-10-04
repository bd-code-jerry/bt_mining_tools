from __future__ import annotations

import sqlite3
from datetime import date


def history_bounds(conn: sqlite3.Connection, workspace_id: int) -> tuple[str | None, str | None]:
    row = conn.execute(
        """SELECT MIN(entry_date) AS first_date, MAX(entry_date) AS last_date
           FROM history_entries WHERE workspace_id = ?""",
        (workspace_id,),
    ).fetchone()
    if not row:
        return None, None
    return row["first_date"], row["last_date"]


def latest_history_date(conn: sqlite3.Connection, workspace_id: int) -> date | None:
    row = conn.execute(
        "SELECT MAX(entry_date) AS latest_date FROM history_entries WHERE workspace_id = ?",
        (workspace_id,),
    ).fetchone()
    raw = row["latest_date"] if row else None
    return date.fromisoformat(raw) if raw else None


def aggregate_all_time(conn: sqlite3.Connection, workspace_id: int) -> list[dict]:
    rows = conn.execute(
        """SELECT p.provider_key, p.display_name, p.unit, p.sort_order,
                  COALESCE(SUM(hv.used_balance), 0) AS total_used
           FROM providers p
           LEFT JOIN history_entries he ON he.workspace_id = ?
           LEFT JOIN history_values hv ON hv.entry_id = he.id AND hv.provider_id = p.id
           GROUP BY p.id ORDER BY p.sort_order""",
        (workspace_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def aggregate_range(
    conn: sqlite3.Connection,
    workspace_id: int,
    start_date: str,
    end_date: str,
) -> list[dict]:
    rows = conn.execute(
        """SELECT p.provider_key, p.display_name, p.unit, p.sort_order,
                  COALESCE(SUM(hv.used_balance), 0) AS total_used
           FROM providers p
           LEFT JOIN history_entries he
             ON he.workspace_id = ? AND he.entry_date >= ? AND he.entry_date <= ?
           LEFT JOIN history_values hv ON hv.entry_id = he.id AND hv.provider_id = p.id
           GROUP BY p.id ORDER BY p.sort_order""",
        (workspace_id, start_date, end_date),
    ).fetchall()
    return [dict(row) for row in rows]


def history_count(conn: sqlite3.Connection, workspace_id: int, start: str | None, end: str | None) -> int:
    if start is None or end is None:
        return 0
    row = conn.execute(
        """SELECT COUNT(*) AS c FROM history_entries
           WHERE workspace_id = ? AND entry_date >= ? AND entry_date <= ?""",
        (workspace_id, start, end),
    ).fetchone()
    return int(row["c"] if row else 0)
