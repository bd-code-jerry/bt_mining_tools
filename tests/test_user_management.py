from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from backend.app.database import db_connection
from tests.support import AuthenticatedWorkspaceTestCase


class UserManagementTests(AuthenticatedWorkspaceTestCase):
    def create_account(self, username: str, email: str, role: str = "member") -> dict:
        response = self.client.post(
            "/api/users",
            json={
                "username": username,
                "email": email,
                "password": "strong-password-1",
                "role": role,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["user"]

    def test_admin_approval_assigns_role(self) -> None:
        pending = self.client.post(
            "/api/auth/register",
            json={"username": "approved-user", "email": "approved@example.com", "password": "strong-password-1"},
        ).json()["user"]
        approved = self.client.post(
            f"/api/users/pending/{pending['id']}/approve",
            json={"role": "user"},
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["user"]["role"], "user")
        self.assertEqual(approved.json()["user"]["status"], "active")
        with db_connection() as conn:
            workspace = conn.execute(
                "SELECT owner_user_id FROM workspaces WHERE kind = 'private' AND owner_user_id = ?",
                (pending["id"],),
            ).fetchone()
        self.assertIsNotNone(workspace)

    def test_duplicate_identifier_lifecycle(self) -> None:
        pending = self.client.post(
            "/api/auth/register",
            json={"username": "reserved-id", "email": "reserved@example.com", "password": "strong-password-1"},
        ).json()["user"]
        username_conflict = self.client.post(
            "/api/users",
            json={"username": "RESERVED-ID", "email": "new@example.com", "password": "strong-password-1"},
        )
        email_conflict = self.client.post(
            "/api/users",
            json={"username": "new-name", "email": "RESERVED@example.com", "password": "strong-password-1"},
        )
        self.assertEqual(username_conflict.status_code, 409)
        self.assertEqual(email_conflict.status_code, 409)
        removed = self.client.delete(f"/api/users/pending/{pending['id']}")
        self.assertEqual(removed.status_code, 200, removed.text)
        replacement = self.client.post(
            "/api/users",
            json={"username": "reserved-id", "email": "reserved@example.com", "password": "strong-password-1"},
        )
        self.assertEqual(replacement.status_code, 201, replacement.text)

    def test_denial_releases_identifiers(self) -> None:
        pending = self.client.post(
            "/api/auth/register",
            json={"username": "denied-user", "email": "denied@example.com", "password": "strong-password-1"},
        ).json()["user"]
        denied = self.client.delete(f"/api/users/pending/{pending['id']}")
        self.assertEqual(denied.status_code, 200, denied.text)
        retry = self.client.post(
            "/api/auth/register",
            json={"username": "denied-user", "email": "denied@example.com", "password": "strong-password-1"},
        )
        self.assertEqual(retry.status_code, 202, retry.text)

    def test_registration_toggle_blocks_self_registration_but_allows_admin_creation(self) -> None:
        toggled = self.client.patch("/api/users/registration", json={"enabled": False})
        self.assertEqual(toggled.status_code, 200, toggled.text)
        public = self.client.post(
            "/api/auth/register",
            json={"username": "public-user", "email": "public@example.com", "password": "strong-password-1"},
        )
        self.assertEqual(public.status_code, 403)
        direct = self.create_account("admin-added", "admin-added@example.com")
        self.assertEqual(direct["status"], "active")
        self.assertNotIn("password_hash", direct)
        self.assertNotIn("password", direct)

    def test_role_changes_create_and_reuse_private_workspace(self) -> None:
        account = self.create_account("workspace-role", "workspace-role@example.com")
        user_id = account["id"]
        to_user = self.client.patch(f"/api/users/{user_id}/role", json={"role": "user"})
        self.assertEqual(to_user.status_code, 200, to_user.text)
        with db_connection() as conn:
            first = conn.execute(
                "SELECT id FROM workspaces WHERE kind = 'private' AND owner_user_id = ?", (user_id,)
            ).fetchone()["id"]
        self.assertEqual(self.client.patch(f"/api/users/{user_id}/role", json={"role": "member"}).status_code, 200)
        again = self.client.patch(f"/api/users/{user_id}/role", json={"role": "user"})
        self.assertEqual(again.status_code, 200, again.text)
        with db_connection() as conn:
            second = conn.execute(
                "SELECT id FROM workspaces WHERE kind = 'private' AND owner_user_id = ?", (user_id,)
            ).fetchone()["id"]
        self.assertEqual(first, second)

    def test_reset_and_disable_revoke_sessions(self) -> None:
        account = self.create_account("session-user", "session-user@example.com")
        with TestClient(self.client.app) as user_client:
            login = user_client.post(
                "/api/auth/login", json={"identifier": account["username"], "password": "strong-password-1"}
            )
            self.assertEqual(login.status_code, 200, login.text)
            session_list = self.client.get(f"/api/users/{account['id']}/sessions").json()["sessions"]
            self.assertEqual(len(session_list), 1)
            self.assertNotIn("token_hash", session_list[0])
            self.assertNotIn("ip_address", session_list[0])
            revoked = self.client.delete(f"/api/users/sessions/{session_list[0]['id']}")
            self.assertEqual(revoked.status_code, 200, revoked.text)
            self.assertEqual(user_client.get("/api/auth/me").status_code, 401)
            self.assertEqual(
                user_client.post(
                    "/api/auth/login", json={"identifier": account["username"], "password": "strong-password-1"}
                ).status_code,
                200,
            )
            reset = self.client.post(
                f"/api/users/{account['id']}/password-reset",
                json={"new_password": "new-strong-password-2"},
            )
            self.assertEqual(reset.status_code, 200, reset.text)
            self.assertNotIn("password", reset.text.lower())
            self.assertEqual(self.client.get(f"/api/users/{account['id']}/sessions").json()["sessions"], [])
            self.assertEqual(user_client.get("/api/auth/me").status_code, 401)
            relogin = user_client.post(
                "/api/auth/login", json={"identifier": account["email"], "password": "new-strong-password-2"}
            )
            self.assertEqual(relogin.status_code, 200, relogin.text)
            disabled = self.client.patch(f"/api/users/{account['id']}/status", json={"status": "disabled"})
            self.assertEqual(disabled.status_code, 200, disabled.text)
            self.assertEqual(self.client.get(f"/api/users/{account['id']}/sessions").json()["sessions"], [])
            self.assertEqual(user_client.get("/api/auth/me").status_code, 401)
            denied = user_client.post(
                "/api/auth/login", json={"identifier": account["username"], "password": "new-strong-password-2"}
            )
            self.assertEqual(denied.status_code, 403)

    def test_non_admin_cannot_manage_users(self) -> None:
        account = self.create_account("read-only-member", "read-only@example.com")
        with TestClient(self.client.app) as member_client:
            signed_in = member_client.post(
                "/api/auth/login", json={"identifier": account["username"], "password": "strong-password-1"}
            )
            self.assertEqual(signed_in.status_code, 200, signed_in.text)
            self.assertEqual(member_client.get("/api/users").status_code, 403)
            self.assertEqual(
                member_client.delete(f"/api/users/{account['id']}/sessions").status_code,
                403,
            )
            self.assertEqual(
                member_client.patch(
                    "/api/preferences/timezone", json={"timezone": "America/New_York"}
                ).status_code,
                200,
            )

    def test_admin_can_change_email_with_case_insensitive_uniqueness(self) -> None:
        account = self.create_account("email-change", "original@example.com")
        updated = self.client.patch(f"/api/users/{account['id']}", json={"email": "new-email@example.com"})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["user"]["email"], "new-email@example.com")
        conflict = self.client.patch(
            f"/api/users/{account['id']}", json={"email": "OTHER@EXAMPLE.COM"}
        )
        self.assertEqual(conflict.status_code, 409, conflict.text)

    def test_login_events_survive_logout_and_daily_counts_match(self) -> None:
        account = self.create_account("activity-user", "activity@example.com")
        with TestClient(self.client.app) as user_client:
            for _ in range(2):
                login = user_client.post(
                    "/api/auth/login", json={"identifier": account["username"], "password": "strong-password-1"}
                )
                self.assertEqual(login.status_code, 200, login.text)
                self.assertEqual(user_client.post("/api/auth/logout").status_code, 200)
        events = self.client.get("/api/users/login-events", params={"account_id": account["id"], "role": "member"})
        self.assertEqual(events.status_code, 200, events.text)
        self.assertEqual(len(events.json()["events"]), 2)
        self.assertNotIn("token", events.text.lower())
        self.assertNotIn("ip_address", events.text.lower())
        daily = self.client.get("/api/users/login-events/daily", params={"account_id": account["id"], "role": "member"})
        self.assertEqual(daily.status_code, 200, daily.text)
        self.assertEqual(sum(item["count"] for item in daily.json()["days"]), 2)
        wrong_role = self.client.get("/api/users/login-events", params={"role": "user"})
        self.assertEqual(wrong_role.status_code, 200, wrong_role.text)
        self.assertEqual(wrong_role.json()["events"], [])

    def test_last_admin_protection_and_private_workspace_deletion(self) -> None:
        for path, method, body in (
            (f"/api/users/{self.actor_id}/role", "patch", {"role": "member"}),
            (f"/api/users/{self.actor_id}/status", "patch", {"status": "disabled"}),
            (f"/api/users/{self.actor_id}", "delete", None),
        ):
            response = self.client.request(method.upper(), path, json=body)
            self.assertEqual(response.status_code, 409, response.text)

        account = self.create_account("delete-user", "delete-user@example.com", role="user")
        with TestClient(self.client.app) as user_client:
            user_client.post(
                "/api/auth/login", json={"identifier": account["username"], "password": "strong-password-1"}
            )
            user_client.get("/api/workspaces")
        with db_connection() as conn:
            private_workspace_id = conn.execute(
                "SELECT id FROM workspaces WHERE owner_user_id = ?", (account["id"],)
            ).fetchone()["id"]
            conn.execute(
                "INSERT INTO history_entries(entry_date, created_at, updated_at, created_by, updated_by, workspace_id) VALUES ('2035-03-01', '2035-03-01T00:00:00+00:00', '2035-03-01T00:00:00+00:00', ?, ?, ?)",
                (account["id"], account["id"], private_workspace_id),
            )
            conn.execute(
                "INSERT INTO history_entries(entry_date, created_at, updated_at, created_by, updated_by, workspace_id) VALUES ('2035-03-02', '2035-03-02T00:00:00+00:00', '2035-03-02T00:00:00+00:00', ?, ?, ?)",
                (account["id"], account["id"], self.shared_id),
            )
        deleted = self.client.delete(f"/api/users/{account['id']}")
        self.assertEqual(deleted.status_code, 200, deleted.text)
        with db_connection() as conn:
            self.assertIsNone(conn.execute("SELECT 1 FROM users WHERE id = ?", (account["id"],)).fetchone())
            self.assertIsNone(conn.execute("SELECT 1 FROM workspaces WHERE id = ?", (private_workspace_id,)).fetchone())
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM history_entries WHERE workspace_id = ?", (private_workspace_id,)).fetchone()[0], 0)
            shared = conn.execute("SELECT created_by, updated_by FROM history_entries WHERE entry_date = '2035-03-02'").fetchone()
            self.assertEqual(tuple(shared), (None, None))
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM login_events WHERE user_id = ?", (account["id"],)).fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
