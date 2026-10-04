from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


VERSION = 2
NAME = "roles_workspaces"


def _add_column(conn: sqlite3.Connection, table: str, column_sql: str) -> None:
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_sql}")


def apply(conn: sqlite3.Connection, *, initial_admin_username: str | None = None) -> None:
    _add_column(conn, "users", "email TEXT")
    _add_column(
        conn,
        "users",
        "role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member', 'user'))",
    )
    _add_column(
        conn,
        "users",
        "status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('pending', 'active', 'disabled'))",
    )
    _add_column(conn, "users", "last_login_at TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX idx_users_email_nocase ON users(email COLLATE NOCASE) "
        "WHERE email IS NOT NULL AND trim(email) <> ''"
    )
    conn.execute(
        "CREATE INDEX idx_users_status_role ON users(status, role, username COLLATE NOCASE)"
    )

    if initial_admin_username:
        conn.execute(
            "UPDATE users SET role = CASE WHEN username = ? COLLATE NOCASE THEN 'admin' ELSE 'member' END, "
            "status = 'active'",
            (initial_admin_username.strip(),),
        )
    else:
        conn.execute("UPDATE users SET role = 'member', status = 'active'")

    _add_column(conn, "sessions", "last_activity_at TEXT NOT NULL DEFAULT ''")
    conn.execute("UPDATE sessions SET last_activity_at = created_at WHERE last_activity_at = ''")
    conn.execute(
        """CREATE TABLE login_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            signed_in_at TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'member', 'user')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )"""
    )
    conn.execute("CREATE INDEX idx_login_events_signed_in_at ON login_events(signed_in_at DESC, id DESC)")
    conn.execute("CREATE INDEX idx_login_events_user_time ON login_events(user_id, signed_in_at DESC)")

    conn.execute(
        """CREATE TABLE workspaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL CHECK (kind IN ('shared', 'private')),
            owner_user_id INTEGER,
            display_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            CHECK ((kind = 'shared' AND owner_user_id IS NULL) OR (kind = 'private' AND owner_user_id IS NOT NULL)),
            FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE
        )"""
    )
    conn.execute("CREATE UNIQUE INDEX idx_workspaces_shared ON workspaces(kind) WHERE kind = 'shared'")
    conn.execute(
        "CREATE UNIQUE INDEX idx_workspaces_private_owner ON workspaces(owner_user_id) WHERE kind = 'private'"
    )
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO workspaces(kind, owner_user_id, display_name, created_at) VALUES ('shared', NULL, ?, ?)",
        ("Shared workspace", now),
    )
    shared_workspace_id = int(conn.execute("SELECT id FROM workspaces WHERE kind = 'shared'").fetchone()[0])

    conn.execute(
        """CREATE TABLE app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )"""
    )
    conn.execute("INSERT INTO app_settings(key, value) VALUES ('registration_enabled', 'true')")

    conn.execute(
        """CREATE TABLE history_entries_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            created_by INTEGER,
            updated_by INTEGER,
            workspace_id INTEGER NOT NULL,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        )"""
    )
    conn.execute(
        """INSERT INTO history_entries_new(id, entry_date, created_at, updated_at, created_by, updated_by, workspace_id)
           SELECT id, entry_date, created_at, updated_at, created_by, updated_by, ? FROM history_entries""",
        (shared_workspace_id,),
    )
    conn.execute("DROP TABLE history_entries")
    conn.execute("ALTER TABLE history_entries_new RENAME TO history_entries")
    conn.execute(
        "CREATE INDEX idx_history_entries_workspace_date ON history_entries(workspace_id, entry_date DESC, id DESC)"
    )
