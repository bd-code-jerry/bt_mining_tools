from __future__ import annotations

import sqlite3


VERSION = 1
NAME = "base_schema"


def apply(conn: sqlite3.Connection, *, initial_admin_username: str | None = None) -> None:
    statements = (
        """CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""",
        """CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_hash TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""",
        "CREATE INDEX idx_sessions_token_hash ON sessions(token_hash)",
        "CREATE INDEX idx_sessions_expires_at ON sessions(expires_at)",
        """CREATE TABLE providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_key TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            unit TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE history_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            created_by INTEGER,
            updated_by INTEGER,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
        )""",
        "CREATE INDEX idx_history_entries_date ON history_entries(entry_date DESC, id DESC)",
        """CREATE TABLE history_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL,
            provider_id INTEGER NOT NULL,
            total_balance REAL NOT NULL,
            used_balance REAL NOT NULL,
            left_balance REAL NOT NULL,
            UNIQUE(entry_id, provider_id),
            FOREIGN KEY (entry_id) REFERENCES history_entries(id) ON DELETE CASCADE,
            FOREIGN KEY (provider_id) REFERENCES providers(id) ON DELETE CASCADE
        )""",
    )
    for statement in statements:
        conn.execute(statement)
