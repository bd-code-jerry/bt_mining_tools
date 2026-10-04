from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .config import DATABASE_PATH, INITIAL_ADMIN_USERNAME
from ..migrations.runner import migrate_database


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_connection() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database() -> None:
    migrate_database(DATABASE_PATH, initial_admin_username=INITIAL_ADMIN_USERNAME)


def migrate_path(database_path: Path, *, initial_admin_username: str | None = None) -> None:
    """Compatibility helper for explicit migration calls in scripts and tests."""
    migrate_database(database_path, initial_admin_username=initial_admin_username)
