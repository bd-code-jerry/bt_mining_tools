from __future__ import annotations

import sqlite3


def set_timezone(conn: sqlite3.Connection, user_id: int, timezone: str) -> None:
    conn.execute("UPDATE users SET timezone = ? WHERE id = ?", (timezone, user_id))


def get_timezone(conn: sqlite3.Connection, user_id: int) -> str | None:
    row = conn.execute("SELECT timezone FROM users WHERE id = ?", (user_id,)).fetchone()
    return str(row["timezone"]) if row else None
