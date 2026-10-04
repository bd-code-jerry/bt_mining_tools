from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.core import database as core_database
from backend.app.database import db_connection
from backend.app.main import app


def create_legacy_database(path: Path) -> dict[str, int]:
    """Create the pre-migration schema with data that migrations must preserve."""
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_key TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                unit TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE history_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by INTEGER,
                updated_by INTEGER,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
            );
            CREATE INDEX idx_history_entries_date
                ON history_entries(entry_date DESC, id DESC);
            CREATE TABLE history_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id INTEGER NOT NULL,
                provider_id INTEGER NOT NULL,
                total_balance REAL NOT NULL,
                used_balance REAL NOT NULL,
                left_balance REAL NOT NULL,
                UNIQUE(entry_id, provider_id),
                FOREIGN KEY (entry_id) REFERENCES history_entries(id) ON DELETE CASCADE,
                FOREIGN KEY (provider_id) REFERENCES providers(id) ON DELETE CASCADE
            );
            """
        )
        root_id = conn.execute(
            "INSERT INTO users(username, password_hash, created_at) VALUES (?, ?, ?)",
            ("root", "root-hash", "2025-01-01T00:00:00+00:00"),
        ).lastrowid
        member_id = conn.execute(
            "INSERT INTO users(username, password_hash, created_at) VALUES (?, ?, ?)",
            ("viewer", "viewer-hash", "2025-01-02T00:00:00+00:00"),
        ).lastrowid
        conn.execute(
            "INSERT INTO sessions(token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            ("session-hash", root_id, "2025-01-03T00:00:00+00:00", 2000000000),
        )
        provider_id = conn.execute(
            "INSERT INTO providers(provider_key, display_name, unit, sort_order) VALUES (?, ?, ?, ?)",
            ("openrouter", "OpenRouter", "USD", 1),
        ).lastrowid
        entry_id = conn.execute(
            "INSERT INTO history_entries(entry_date, created_at, updated_at, created_by, updated_by) "
            "VALUES (?, ?, ?, ?, ?)",
            ("2025-02-03", "2025-02-03T08:00:00+00:00", "2025-02-03T08:00:00+00:00", root_id, root_id),
        ).lastrowid
        value_id = conn.execute(
            "INSERT INTO history_values(entry_id, provider_id, total_balance, used_balance, left_balance) "
            "VALUES (?, ?, ?, ?, ?)",
            (entry_id, provider_id, 20.0, 3.5, 16.5),
        ).lastrowid
        conn.commit()
        return {
            "root_id": int(root_id),
            "member_id": int(member_id),
            "provider_id": int(provider_id),
            "entry_id": int(entry_id),
            "value_id": int(value_id),
        }
    finally:
        conn.close()


class AuthenticatedWorkspaceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_database_path = core_database.DATABASE_PATH
        core_database.DATABASE_PATH = Path(self.temp_dir.name) / "workspaces.sqlite3"
        self.client = TestClient(app)
        self.client.__enter__()
        response = self.client.post(
            "/api/auth/register",
            json={
                "username": "workspace-admin",
                "email": "workspace-admin@example.com",
                "password": "strong-password-1",
            },
        )
        if response.status_code != 200:
            raise AssertionError(f"test admin registration failed: {response.status_code} {response.text}")
        self.actor_id = int(response.json()["user"]["id"])
        with db_connection() as conn:
            self.shared_id = int(
                conn.execute("SELECT id FROM workspaces WHERE kind = 'shared'").fetchone()[0]
            )
            self.provider_id = int(
                conn.execute("SELECT id FROM providers WHERE provider_key = 'openrouter'").fetchone()[0]
            )
            self.other_user_id = int(
                conn.execute(
                    """INSERT INTO users(username, email, password_hash, created_at, role, status)
                       VALUES ('other-user', 'other@example.com', 'unused-hash', ?, 'user', 'active')""",
                    (datetime.now(timezone.utc).isoformat(timespec="seconds"),),
                ).lastrowid
            )
            self.own_workspace_id = self.create_private_workspace(conn, self.actor_id, "Workspace Admin")
            self.other_workspace_id = self.create_private_workspace(conn, self.other_user_id, "Other User")

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        core_database.DATABASE_PATH = self.previous_database_path
        self.temp_dir.cleanup()

    @staticmethod
    def create_private_workspace(conn, owner_id: int, label: str) -> int:
        cursor = conn.execute(
            "INSERT INTO workspaces(kind, owner_user_id, display_name, created_at) VALUES ('private', ?, ?, ?)",
            (owner_id, label, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        return int(cursor.lastrowid)

    def add_history(
        self,
        workspace_id: int,
        entry_date: str,
        *,
        total: float = 20.0,
        used: float = 2.0,
        left: float = 18.0,
    ) -> int:
        with db_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO history_entries(entry_date, created_at, updated_at, created_by, updated_by, workspace_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (entry_date, f"{entry_date}T00:00:00+00:00", f"{entry_date}T00:00:00+00:00", self.actor_id, self.actor_id, workspace_id),
            )
            entry_id = int(cursor.lastrowid)
            conn.execute(
                """INSERT INTO history_values(entry_id, provider_id, total_balance, used_balance, left_balance)
                   VALUES (?, ?, ?, ?, ?)""",
                (entry_id, self.provider_id, total, used, left),
            )
            return entry_id

    def set_actor_role(self, role: str) -> None:
        with db_connection() as conn:
            conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, self.actor_id))
