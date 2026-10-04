from __future__ import annotations

import unittest
import zoneinfo
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.database import db_connection
from tests.support import AuthenticatedWorkspaceTestCase
from backend.app.features.preferences.service import zone_for


class TimezoneDataPackagingTests(unittest.TestCase):
    def test_timezone_database_is_a_runtime_dependency_for_hosts_without_iana_data(self) -> None:
        requirements = Path(__file__).resolve().parents[1] / "requirements.txt"
        declared = requirements.read_text(encoding="utf-8").splitlines()
        self.assertTrue(any(line.strip().lower().startswith("tzdata") for line in declared))

    def test_eastern_time_converts_when_the_host_has_no_system_timezone_database(self) -> None:
        previous_path = zoneinfo.TZPATH
        try:
            zoneinfo.reset_tzpath(())
            eastern = zone_for("America/New_York")
            converted = datetime(2024, 3, 10, 7, 0, tzinfo=timezone.utc).astimezone(eastern)
            self.assertEqual(converted.isoformat(), "2024-03-10T03:00:00-04:00")
        finally:
            zoneinfo.reset_tzpath(previous_path)


class PreferenceTests(AuthenticatedWorkspaceTestCase):
    def create_account(self, username: str, email: str, role: str) -> dict:
        response = self.client.post(
            "/api/users",
            json={"username": username, "email": email, "password": "strong-password-1", "role": role},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["user"]

    def test_timezone_preference_is_per_account_and_available_to_all_roles(self) -> None:
        admin_change = self.client.patch(
            "/api/preferences/timezone", json={"timezone": "America/New_York"}
        )
        self.assertEqual(admin_change.status_code, 200, admin_change.text)
        self.assertEqual(self.client.get("/api/auth/me").json()["user"]["timezone"], "America/New_York")
        self.assertEqual(
            self.client.patch("/api/preferences/timezone", json={"timezone": "UTC"}).status_code,
            200,
        )
        accounts = [
            self.create_account("timezone-member", "timezone-member@example.com", "member"),
            self.create_account("timezone-user", "timezone-user@example.com", "user"),
        ]
        for account in accounts:
            with TestClient(self.client.app) as role_client:
                signed_in = role_client.post(
                    "/api/auth/login",
                    json={"identifier": account["username"], "password": "strong-password-1"},
                )
                self.assertEqual(signed_in.status_code, 200, signed_in.text)
                changed = role_client.patch(
                    "/api/preferences/timezone", json={"timezone": "America/New_York"}
                )
                self.assertEqual(changed.status_code, 200, changed.text)
                self.assertEqual(changed.json()["timezone"], "America/New_York")
                self.assertEqual(role_client.get("/api/auth/me").json()["user"]["timezone"], "America/New_York")
        with db_connection() as conn:
            timezones = {
                row["username"]: row["timezone"]
                for row in conn.execute(
                    "SELECT username, timezone FROM users WHERE username IN (?, ?, ?)",
                    ("workspace-admin", "timezone-member", "timezone-user"),
                )
            }
        self.assertEqual(timezones, {
            "workspace-admin": "UTC",
            "timezone-member": "America/New_York",
            "timezone-user": "America/New_York",
        })

    def test_unsupported_timezone_is_rejected(self) -> None:
        rejected = self.client.patch("/api/preferences/timezone", json={"timezone": "Europe/London"})
        self.assertEqual(rejected.status_code, 422, rejected.text)
        self.assertEqual(self.client.get("/api/auth/me").json()["user"]["timezone"], "UTC")


if __name__ == "__main__":
    unittest.main()
