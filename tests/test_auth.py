from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.core import database as core_database
from backend.app.database import db_connection
from backend.app.main import app


class AuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_database_path = core_database.DATABASE_PATH
        core_database.DATABASE_PATH = Path(self.temp_dir.name) / "auth.sqlite3"
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        core_database.DATABASE_PATH = self.previous_database_path
        self.temp_dir.cleanup()

    def register(self, username: str, email: str) -> object:
        return self.client.post(
            "/api/auth/register",
            json={"username": username, "email": email, "password": "strong-password-1"},
        )

    def event_count(self) -> int:
        with db_connection() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM login_events").fetchone()[0])

    def test_first_registration_becomes_admin(self) -> None:
        response = self.register("first-admin", "admin@example.com")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["user"].get("role"), "admin")
        self.assertEqual(response.json()["user"].get("status"), "active")
        self.assertNotIn("password_hash", response.json()["user"])
        current = self.client.get("/api/auth/me").json()["user"]
        self.assertEqual(current.get("role"), "admin")
        self.assertEqual(current.get("timezone"), "UTC")
        self.assertIn("users:manage", current.get("capabilities", []))
        self.assertEqual(self.event_count(), 1)
        with db_connection() as conn:
            account = conn.execute("SELECT last_login_at FROM users WHERE username = 'first-admin'").fetchone()
            event = conn.execute("SELECT role FROM login_events").fetchone()
        self.assertIsNotNone(account["last_login_at"])
        self.assertEqual(event["role"], "admin")

    def test_authenticated_request_updates_session_activity(self) -> None:
        self.register("first-admin", "admin@example.com")
        with patch(
            "backend.app.core.dependencies.utc_now_iso",
            return_value="2030-01-02T03:04:05+00:00",
        ):
            response = self.client.get("/api/auth/me")
        self.assertEqual(response.status_code, 200)
        with db_connection() as conn:
            row = conn.execute("SELECT last_activity_at FROM sessions").fetchone()
        self.assertEqual(row["last_activity_at"], "2030-01-02T03:04:05+00:00")

    def test_later_registration_is_pending_without_session(self) -> None:
        self.assertEqual(self.register("first-admin", "admin@example.com").status_code, 200)
        self.client.post("/api/auth/logout")
        response = self.register("waiting-user", "waiting@example.com")
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(response.json()["status"], "pending")
        self.assertNotIn("set-cookie", response.headers)
        login = self.client.post(
            "/api/auth/login",
            json={"identifier": "waiting-user", "password": "strong-password-1"},
        )
        self.assertEqual(login.status_code, 403)
        self.assertEqual(self.event_count(), 1)

    def test_login_accepts_username_or_email(self) -> None:
        self.register("first-admin", "admin@example.com")
        self.client.post("/api/auth/logout")
        by_email = self.client.post(
            "/api/auth/login",
            json={"identifier": "admin@example.com", "password": "strong-password-1"},
        )
        self.assertEqual(by_email.status_code, 200, by_email.text)
        self.client.post("/api/auth/logout")
        by_username = self.client.post(
            "/api/auth/login",
            json={"identifier": "FIRST-ADMIN", "password": "strong-password-1"},
        )
        self.assertEqual(by_username.status_code, 200, by_username.text)
        self.assertEqual(self.event_count(), 3)

    def test_pending_and_disabled_users_cannot_sign_in(self) -> None:
        self.register("first-admin", "admin@example.com")
        pending = self.register("waiting-user", "waiting@example.com")
        pending_id = pending.json()["user"]["id"]
        self.client.post("/api/auth/logout")
        denied_pending = self.client.post(
            "/api/auth/login",
            json={"identifier": "waiting-user", "password": "strong-password-1"},
        )
        self.assertEqual(denied_pending.status_code, 403)
        with db_connection() as conn:
            conn.execute("UPDATE users SET status = 'disabled' WHERE id = ?", (pending_id,))
        denied_disabled = self.client.post(
            "/api/auth/login",
            json={"identifier": "waiting@example.com", "password": "strong-password-1"},
        )
        self.assertEqual(denied_disabled.status_code, 403)
        self.assertEqual(self.event_count(), 1)

    def test_duplicate_identifier_lifecycle(self) -> None:
        self.register("first-admin", "admin@example.com")
        pending = self.register("reserved-name", "reserved@example.com")
        pending_id = pending.json()["user"]["id"]
        self.client.post("/api/auth/logout")
        duplicate_username = self.register("RESERVED-NAME", "new@example.com")
        duplicate_email = self.register("other-name", "RESERVED@example.com")
        self.assertEqual(duplicate_username.status_code, 409)
        self.assertEqual(duplicate_email.status_code, 409)
        with db_connection() as conn:
            conn.execute("UPDATE users SET status = 'disabled' WHERE id = ?", (pending_id,))
        self.assertEqual(self.register("reserved-name", "new@example.com").status_code, 409)
        with db_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (pending_id,))
        released = self.register("reserved-name", "reserved@example.com")
        self.assertEqual(released.status_code, 202, released.text)

    def test_registration_code_is_enforced(self) -> None:
        with patch("backend.app.core.config.REGISTRATION_CODE", "invite-only"):
            rejected = self.client.post(
                "/api/auth/register",
                json={
                    "username": "first-admin",
                    "email": "admin@example.com",
                    "password": "strong-password-1",
                    "registration_code": "wrong",
                },
            )
            accepted = self.client.post(
                "/api/auth/register",
                json={
                    "username": "first-admin",
                    "email": "admin@example.com",
                    "password": "strong-password-1",
                    "registration_code": "invite-only",
                },
            )
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(accepted.status_code, 200, accepted.text)

    def test_failed_login_creates_no_event(self) -> None:
        self.register("first-admin", "admin@example.com")
        self.client.post("/api/auth/logout")
        before = self.event_count()
        failed = self.client.post(
            "/api/auth/login",
            json={"identifier": "first-admin", "password": "wrong-password"},
        )
        self.assertEqual(failed.status_code, 401)
        self.assertEqual(self.event_count(), before)

    def test_concurrent_first_registrations_create_one_admin(self) -> None:
        registrations = [
            ("race-one", "one@example.com"),
            ("race-two", "two@example.com"),
        ]

        def create_account(args: tuple[str, str]) -> dict[str, object]:
            username, email = args
            try:
                from backend.app.features.auth.service import register_account
            except ImportError:
                return {"role": "missing", "status": "missing"}
            with db_connection() as conn:
                return register_account(
                    conn,
                    username=username,
                    email=email,
                    password="strong-password-1",
                    registration_code=None,
                )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(create_account, registrations))
        roles = [str(result["role"]) for result in results]
        statuses = [str(result["status"]) for result in results]
        self.assertEqual(roles.count("admin"), 1)
        self.assertEqual(statuses.count("pending"), 1)
        with db_connection() as conn:
            count = int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])
        self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
