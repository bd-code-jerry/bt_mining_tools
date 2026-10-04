from __future__ import annotations

from backend.app.database import db_connection
from tests.support import AuthenticatedWorkspaceTestCase


class WorkspacePermissionTests(AuthenticatedWorkspaceTestCase):
    @staticmethod
    def dates(response) -> list[str]:
        return [entry["entry_date"] for entry in response.json()["history"]]

    def test_admin_can_select_any_workspace(self) -> None:
        self.add_history(self.shared_id, "2025-01-01")
        self.add_history(self.own_workspace_id, "2025-01-02")
        self.add_history(self.other_workspace_id, "2025-01-03")
        workspaces = self.client.get("/api/workspaces")
        self.assertEqual(workspaces.status_code, 200, workspaces.text)
        self.assertEqual(
            {item["id"] for item in workspaces.json()["workspaces"]},
            {self.shared_id, self.own_workspace_id, self.other_workspace_id},
        )
        overview = self.client.get(
            f"/api/balances/overview?workspace_id={self.other_workspace_id}"
        )
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(self.dates(overview), ["2025-01-03"])

    def test_member_reads_shared_workspace_only(self) -> None:
        self.add_history(self.shared_id, "2025-01-01")
        self.add_history(self.own_workspace_id, "2025-01-02")
        self.set_actor_role("member")
        workspaces = self.client.get("/api/workspaces")
        self.assertEqual(workspaces.status_code, 200, workspaces.text)
        self.assertEqual([item["id"] for item in workspaces.json()["workspaces"]], [self.shared_id])
        overview = self.client.get(f"/api/balances/overview?workspace_id={self.shared_id}")
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(self.dates(overview), ["2025-01-01"])

    def test_member_cannot_mutate_shared_balances(self) -> None:
        self.set_actor_role("member")
        response = self.client.post(
            f"/api/balances/history?workspace_id={self.shared_id}",
            json={"entry_date": "2025-01-05", "expected_latest_entry_id": None, "values": {}},
        )
        self.assertEqual(response.status_code, 403, response.text)
        with db_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM history_entries").fetchone()[0]
        self.assertEqual(count, 0)

    def test_user_reads_and_edits_own_workspace_only(self) -> None:
        own_entry_id = self.add_history(self.own_workspace_id, "2025-02-01")
        other_entry_id = self.add_history(self.other_workspace_id, "2025-01-01")
        self.add_history(self.shared_id, "2025-01-15")
        self.set_actor_role("user")
        overview = self.client.get(
            f"/api/balances/overview?workspace_id={self.own_workspace_id}"
        )
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(self.dates(overview), ["2025-02-01"])
        saved = self.client.post(
            f"/api/balances/history?workspace_id={self.own_workspace_id}",
            json={
                "entry_date": "2025-02-02",
                "expected_latest_entry_id": own_entry_id,
                "values": {"openrouter": {"total": 20, "used": 2, "left": 18}},
            },
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        new_entry_id = saved.json()["entry"]["id"]
        with db_connection() as conn:
            saved_workspace_id = conn.execute(
                "SELECT workspace_id FROM history_entries WHERE id = ?", (new_entry_id,)
            ).fetchone()[0]
        self.assertEqual(saved_workspace_id, self.own_workspace_id)

        updated = self.client.put(
            f"/api/balances/history/{new_entry_id}?workspace_id={self.own_workspace_id}",
            json={
                "entry_date": "2025-02-03",
                "values": {"openrouter": {"total": 20, "used": 3, "left": 17}},
            },
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        hidden_entry = self.client.put(
            f"/api/balances/history/{other_entry_id}?workspace_id={self.own_workspace_id}",
            json={"entry_date": "2025-02-04", "values": {}},
        )
        self.assertEqual(hidden_entry.status_code, 404)

    def test_workspace_id_cannot_escalate_role(self) -> None:
        self.set_actor_role("user")
        forbidden = self.client.get(
            f"/api/balances/overview?workspace_id={self.other_workspace_id}"
        )
        unknown = self.client.get("/api/balances/overview?workspace_id=999999")
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(unknown.status_code, 404)


if __name__ == "__main__":
    import unittest

    unittest.main()
