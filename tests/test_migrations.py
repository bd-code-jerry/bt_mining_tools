from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.support import create_legacy_database


class MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.database_path = self.root / "legacy.sqlite3"
        self.ids = create_legacy_database(self.database_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def migrate(self, path: Path | None = None, initial_admin_username: str | None = "root") -> None:
        try:
            from backend.app.migrations.runner import migrate_database
        except ImportError:
            self.fail("the versioned SQLite migration runner is missing")
        migrate_database(path or self.database_path, initial_admin_username=initial_admin_username)

    def test_invalid_initial_admin_leaves_legacy_database_unchanged(self) -> None:
        before = self.database_path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "BD_INITIAL_ADMIN_USERNAME") as raised:
            self.migrate(initial_admin_username="missing-account")
        self.assertIn(str(self.database_path), str(raised.exception))
        self.assertIn("v2", str(raised.exception))
        self.assertEqual(self.database_path.read_bytes(), before)

    def test_existing_database_backup_contains_pre_migration_schema(self) -> None:
        self.migrate()
        backups = list((self.root / "backups").glob("legacy.sqlite3.*.pre-migration.sqlite3"))
        self.assertEqual(len(backups), 1)
        with sqlite3.connect(backups[0]) as backup:
            tables = {row[0] for row in backup.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            columns = {row[1] for row in backup.execute("PRAGMA table_info(history_entries)")}
        self.assertIn("history_values", tables)
        self.assertNotIn("workspaces", tables)
        self.assertNotIn("schema_migrations", tables)
        self.assertNotIn("workspace_id", columns)

    def test_existing_users_receive_selected_admin_and_member_roles(self) -> None:
        self.migrate()
        with sqlite3.connect(self.database_path) as conn:
            conn.row_factory = sqlite3.Row
            users = {row["username"]: row for row in conn.execute("SELECT * FROM users")}
            history = conn.execute(
                "SELECT h.workspace_id, h.created_by, v.total_balance, v.used_balance, v.left_balance "
                "FROM history_entries h JOIN history_values v ON v.entry_id = h.id WHERE h.id = ?",
                (self.ids["entry_id"],),
            ).fetchone()
            session = conn.execute(
                "SELECT token_hash, created_at, last_activity_at FROM sessions WHERE user_id = ?",
                (self.ids["root_id"],),
            ).fetchone()
            provider = conn.execute(
                "SELECT provider_key, display_name, unit FROM providers WHERE id = ?",
                (self.ids["provider_id"],),
            ).fetchone()
            events = conn.execute("SELECT COUNT(*) FROM login_events").fetchone()[0]
            shared = conn.execute("SELECT id FROM workspaces WHERE kind = 'shared'").fetchone()[0]
        self.assertEqual(users["root"]["role"], "admin")
        self.assertEqual(users["root"]["status"], "active")
        self.assertEqual(users["viewer"]["role"], "member")
        self.assertEqual(users["viewer"]["status"], "active")
        self.assertIsNone(users["root"]["email"])
        self.assertIsNone(users["root"]["last_login_at"])
        self.assertEqual(history["workspace_id"], shared)
        self.assertEqual(history["created_by"], self.ids["root_id"])
        self.assertEqual((history["total_balance"], history["used_balance"], history["left_balance"]), (20.0, 3.5, 16.5))
        self.assertEqual(session["token_hash"], "session-hash")
        self.assertEqual(session["last_activity_at"], session["created_at"])
        self.assertEqual(tuple(provider), ("openrouter", "OpenRouter", "USD"))
        self.assertEqual(events, 0)

    def test_fresh_database_does_not_require_initial_admin(self) -> None:
        fresh_path = self.root / "fresh.sqlite3"
        self.migrate(path=fresh_path, initial_admin_username=None)
        with sqlite3.connect(fresh_path) as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            versions = [row[0] for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
            shared_count = conn.execute("SELECT COUNT(*) FROM workspaces WHERE kind = 'shared'").fetchone()[0]
            user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        self.assertIn("history_values", tables)
        self.assertEqual(versions, [1, 2, 3, 4, 5])
        self.assertEqual(shared_count, 1)
        self.assertEqual(user_count, 0)

    def test_migrations_are_repeatable(self) -> None:
        self.migrate()
        self.migrate()
        with sqlite3.connect(self.database_path) as conn:
            versions = [row[0] for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
            workspace_count = conn.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0]
            value = conn.execute("SELECT total_balance FROM history_values WHERE id = ?", (self.ids["value_id"],)).fetchone()[0]
        self.assertEqual(versions, [1, 2, 3, 4, 5])
        self.assertEqual(workspace_count, 1)
        self.assertEqual(value, 20.0)

    def test_v2_foreign_key_failure_rolls_back_schema_and_version_record(self) -> None:
        from backend.app.migrations import runner

        original_apply = runner.v002_roles_workspaces.apply

        def apply_with_orphan(conn, *, initial_admin_username=None):
            original_apply(conn, initial_admin_username=initial_admin_username)
            conn.execute(
                "INSERT INTO history_values(entry_id, provider_id, total_balance, used_balance, left_balance) "
                "VALUES (?, ?, 1, 0, 1)",
                (999999, self.ids["provider_id"]),
            )

        with patch.object(runner.v002_roles_workspaces, "apply", side_effect=apply_with_orphan):
            with self.assertRaisesRegex(RuntimeError, "foreign-key validation"):
                self.migrate()

        with sqlite3.connect(self.database_path) as conn:
            versions = [row[0] for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
            history_columns = {row[1] for row in conn.execute("PRAGMA table_info(history_entries)")}
            values = conn.execute("SELECT COUNT(*) FROM history_values").fetchone()[0]
        self.assertEqual(versions, [1])
        self.assertNotIn("workspace_id", history_columns)
        self.assertEqual(values, 1)

    def test_migrated_users_default_to_utc(self) -> None:
        self.migrate()
        with sqlite3.connect(self.database_path) as conn:
            zones = [row[0] for row in conn.execute("SELECT timezone FROM users ORDER BY id")]
            default_sql = conn.execute("PRAGMA table_info(users)").fetchall()
        timezone_column = next(row for row in default_sql if row[1] == "timezone")
        self.assertEqual(zones, ["UTC", "UTC"])
        self.assertEqual(timezone_column[4], "'UTC'")


if __name__ == "__main__":
    unittest.main()
