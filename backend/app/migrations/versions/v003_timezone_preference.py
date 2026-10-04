from __future__ import annotations

import sqlite3


VERSION = 3
NAME = "timezone_preference"


def apply(conn: sqlite3.Connection, *, initial_admin_username: str | None = None) -> None:
    conn.execute(
        "ALTER TABLE users ADD COLUMN timezone TEXT NOT NULL DEFAULT 'UTC' "
        "CHECK (timezone IN ('UTC', 'America/New_York'))"
    )
