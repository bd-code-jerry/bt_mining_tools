from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, local

from fastapi import HTTPException
from pydantic import ValidationError

from backend.app import database
from backend.app import config
from backend.app.core import database as core_database
from backend.app.database import db_connection, utc_now_iso
from backend.app.features.balances import repository as balance_repository
from backend.app.features.balances.provider_catalog import seed_provider_catalog
from backend.app.features.balances.schemas import CreateHistoryBody
from backend.app.features.balances.service import (
    create_add_balance_entry,
    create_history_entry,
    history_count,
    latest_entry,
)


class BalanceIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_database_path = core_database.DATABASE_PATH
        core_database.DATABASE_PATH = Path(self.temp_dir.name) / "dashboard.sqlite3"
        database.init_database()

        with db_connection() as conn:
            seed_provider_catalog(conn)
            self.workspace_id = int(
                conn.execute("SELECT id FROM workspaces WHERE kind = 'shared'").fetchone()["id"]
            )
            cursor = conn.execute(
                "INSERT INTO users(username, password_hash, created_at) VALUES (?, ?, ?)",
                ("test-user", "not-used", utc_now_iso()),
            )
            self.user_id = cursor.lastrowid

    def tearDown(self) -> None:
        core_database.DATABASE_PATH = self.previous_database_path
        self.temp_dir.cleanup()

    def _create_initial_openrouter_balance(self) -> int:
        with db_connection() as conn:
            entry = create_history_entry(
                conn,
                self.user_id,
                {
                    "expected_latest_entry_id": None,
                    "entry_date": "2035-01-01",
                    "values": {
                        "openrouter": {"total": 13.5, "used": 0.0, "left": 13.5}
                    },
                },
                workspace_id=self.workspace_id,
            )
        return entry["id"]

    def test_balance_service_writes_to_the_shared_workspace(self) -> None:
        entry_id = self._create_initial_openrouter_balance()
        with db_connection() as conn:
            shared_id = conn.execute(
                "SELECT id FROM workspaces WHERE kind = 'shared'"
            ).fetchone()["id"]
            entry = conn.execute(
                "SELECT workspace_id FROM history_entries WHERE id = ?", (entry_id,)
            ).fetchone()
        self.assertEqual(entry["workspace_id"], shared_id)

    def test_first_run_seeds_provider_catalog_without_personal_history(self) -> None:
        with db_connection() as conn:
            providers = conn.execute("SELECT COUNT(*) AS n FROM providers").fetchone()["n"]
            entries = history_count(conn, self.workspace_id)

        self.assertEqual(providers, 8)
        self.assertEqual(entries, 0)

    def test_new_balance_rejects_a_stale_latest_entry_id(self) -> None:
        old_latest_id = self._create_initial_openrouter_balance()
        with db_connection() as conn:
            create_add_balance_entry(
                conn,
                self.user_id,
                {"entry_date": "2035-01-02", "additions": {"openrouter": 1.0}},
                workspace_id=self.workspace_id,
            )

        stale_payload = {
            "expected_latest_entry_id": old_latest_id,
            "entry_date": "2035-01-03",
            "values": {
                "openrouter": {"total": 13.5, "used": 1.0, "left": 12.5}
            },
        }
        with self.assertRaises(HTTPException) as raised:
            with db_connection() as conn:
                create_history_entry(conn, self.user_id, stale_payload, workspace_id=self.workspace_id)

        self.assertEqual(raised.exception.status_code, 409)
        with db_connection() as conn:
            current = latest_entry(conn, self.workspace_id)
        latest_values = {value["provider_key"]: value for value in current["values"]}
        self.assertEqual(latest_values["openrouter"]["left_balance"], 14.5)

    def test_create_history_api_requires_latest_entry_marker(self) -> None:
        with self.assertRaises(ValidationError):
            CreateHistoryBody.model_validate({"values": {}})

        body = CreateHistoryBody.model_validate(
            {"expected_latest_entry_id": None, "values": {}}
        )
        self.assertIsNone(body.expected_latest_entry_id)

    def test_concurrent_topups_apply_both_additions(self) -> None:
        self._create_initial_openrouter_balance()

        original_latest_entry = balance_repository.latest_entry
        worker = local()
        first_read = Event()
        release_first = Event()
        second_read = Event()

        def synchronized_latest_entry(conn, workspace_id):
            result = original_latest_entry(conn, workspace_id)
            label = getattr(worker, "label", None)
            if label == "first":
                first_read.set()
                if not release_first.wait(timeout=10):
                    raise TimeoutError("first top-up was not released")
            elif label == "second":
                second_read.set()
            return result

        balance_repository.latest_entry = synchronized_latest_entry

        def add_one_dollar(label: str) -> None:
            worker.label = label
            with db_connection() as conn:
                create_add_balance_entry(
                    conn,
                    self.user_id,
                    {"entry_date": "2035-01-02", "additions": {"openrouter": 1.0}},
                    workspace_id=self.workspace_id,
                )

        second_read_before_first_commit = False
        second_future = None
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                first_future = pool.submit(add_one_dollar, "first")
                first_reached_read = first_read.wait(timeout=5)
                if first_reached_read:
                    second_future = pool.submit(add_one_dollar, "second")
                    second_read_before_first_commit = second_read.wait(timeout=0.25)
                release_first.set()
                first_future.result(timeout=10)
                if second_future is not None:
                    second_future.result(timeout=10)
        finally:
            release_first.set()
            balance_repository.latest_entry = original_latest_entry

        self.assertTrue(first_reached_read)
        self.assertFalse(second_read_before_first_commit)
        with db_connection() as conn:
            current = latest_entry(conn, self.workspace_id)
        latest_values = {value["provider_key"]: value for value in current["values"]}
        self.assertEqual(latest_values["openrouter"]["left_balance"], 15.5)

    def test_history_rejects_infinite_balance_values(self) -> None:
        with db_connection() as conn:
            entries_before = history_count(conn, self.workspace_id)
        payload = {
            "expected_latest_entry_id": None,
            "entry_date": "2035-01-04",
            "values": {
                "openrouter": {"total": float("inf"), "used": 0.0, "left": float("inf")}
            },
        }

        with self.assertRaises(HTTPException) as raised:
            with db_connection() as conn:
                create_history_entry(conn, self.user_id, payload, workspace_id=self.workspace_id)

        self.assertEqual(raised.exception.status_code, 422)
        with db_connection() as conn:
            self.assertEqual(history_count(conn, self.workspace_id), entries_before)

    def test_topup_rejects_infinite_addition(self) -> None:
        with db_connection() as conn:
            entries_before = history_count(conn, self.workspace_id)
        with self.assertRaises(HTTPException) as raised:
            with db_connection() as conn:
                create_add_balance_entry(
                    conn,
                    self.user_id,
                    {"entry_date": "2035-01-04", "additions": {"openrouter": float("inf")}},
                    workspace_id=self.workspace_id,
                )

        self.assertEqual(raised.exception.status_code, 422)
        with db_connection() as conn:
            self.assertEqual(history_count(conn, self.workspace_id), entries_before)

    def test_topup_rejects_finite_addition_that_overflows_balance(self) -> None:
        with db_connection() as conn:
            create_history_entry(
                conn,
                self.user_id,
                {
                    "expected_latest_entry_id": None,
                    "entry_date": "2035-01-03",
                    "values": {
                        "openrouter": {"total": 1e308, "used": 0.0, "left": 1e308}
                    },
                },
                workspace_id=self.workspace_id,
            )
            entries_before = history_count(conn, self.workspace_id)

        with self.assertRaises(HTTPException) as raised:
            with db_connection() as conn:
                create_add_balance_entry(
                    conn,
                    self.user_id,
                    {"entry_date": "2035-01-04", "additions": {"openrouter": 1e308}},
                    workspace_id=self.workspace_id,
                )

        self.assertEqual(raised.exception.status_code, 422)
        with db_connection() as conn:
            self.assertEqual(history_count(conn, self.workspace_id), entries_before)

    def test_history_rejects_finite_values_that_overflow_derived_total(self) -> None:
        payload = {
            "expected_latest_entry_id": None,
            "entry_date": "2035-01-04",
            "values": {
                "openrouter": {"used": 1e308, "left": 1e308}
            },
        }

        with self.assertRaises(HTTPException) as raised:
            with db_connection() as conn:
                create_history_entry(conn, self.user_id, payload, workspace_id=self.workspace_id)

        self.assertEqual(raised.exception.status_code, 422)
        with db_connection() as conn:
            self.assertEqual(history_count(conn, self.workspace_id), 0)

    def test_nonlocal_bind_requires_registration_code(self) -> None:
        env = os.environ.copy()
        env.update(
            {
                "BD_HOST": "0.0.0.0",
                "BD_REGISTRATION_CODE": "",
                "BD_DATABASE_PATH": str(Path(self.temp_dir.name) / "config.sqlite3"),
            }
        )
        result = subprocess.run(
            [sys.executable, "-c", "import backend.app.config"],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BD_REGISTRATION_CODE", result.stderr)

    def _load_config_values(self, values: dict[str, str]) -> dict[str, object]:
        env = os.environ.copy()
        for key in list(env):
            if key.startswith(("BD_", "RSG_")):
                env.pop(key)
        env.update(values)
        script = (
            "import json; from backend.app import config; "
            "print(json.dumps({'host': config.APP_HOST, 'port': config.APP_PORT, "
            "'registration_code': config.REGISTRATION_CODE, 'session_days': config.SESSION_DAYS, "
            "'cookie_secure': config.COOKIE_SECURE, 'database_path': str(config.DATABASE_PATH), "
            "'cookie_name': config.SESSION_COOKIE_NAME}))"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_bd_settings_take_priority_over_legacy_rsg_settings(self) -> None:
        expected_db = str(Path(self.temp_dir.name) / "bd.sqlite3")
        settings = self._load_config_values(
            {
                "BD_HOST": "127.0.0.1",
                "BD_PORT": "8876",
                "BD_REGISTRATION_CODE": "new-code",
                "BD_SESSION_DAYS": "3",
                "BD_COOKIE_SECURE": "true",
                "BD_DATABASE_PATH": expected_db,
                "RSG_HOST": "127.0.0.2",
                "RSG_PORT": "8877",
                "RSG_REGISTRATION_CODE": "old-code",
                "RSG_SESSION_DAYS": "9",
                "RSG_COOKIE_SECURE": "false",
                "RSG_DATABASE_PATH": str(Path(self.temp_dir.name) / "rsg.sqlite3"),
            }
        )

        self.assertEqual(settings, {
            "host": "127.0.0.1",
            "port": 8876,
            "registration_code": "new-code",
            "session_days": 3,
            "cookie_secure": True,
            "database_path": expected_db,
            "cookie_name": "bd_session",
        })

    def test_rsg_environment_settings_are_ignored(self) -> None:
        expected_db = str(config.PROJECT_ROOT / "data" / "bd_dashboard.db")
        settings = self._load_config_values(
            {
                "RSG_HOST": "0.0.0.0",
                "RSG_PORT": "8878",
                "RSG_REGISTRATION_CODE": "legacy-code",
                "RSG_SESSION_DAYS": "5",
                "RSG_COOKIE_SECURE": "true",
                "RSG_DATABASE_PATH": str(Path(self.temp_dir.name) / "legacy.sqlite3"),
            }
        )

        self.assertEqual(settings["host"], "127.0.0.1")
        self.assertEqual(settings["port"], 8765)
        self.assertEqual(settings["registration_code"], "")
        self.assertEqual(settings["session_days"], 14)
        self.assertFalse(settings["cookie_secure"])
        self.assertEqual(settings["database_path"], expected_db)
        self.assertEqual(settings["cookie_name"], "bd_session")


if __name__ == "__main__":
    unittest.main()
