from __future__ import annotations

from backend.app.database import db_connection
from tests.support import AuthenticatedWorkspaceTestCase


class TotalBalanceTests(AuthenticatedWorkspaceTestCase):
    def add_values(self, workspace_id: int, entry_date: str, values: dict[str, tuple[float, float, float]]) -> int:
        with db_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO history_entries(entry_date, created_at, updated_at, created_by, updated_by, workspace_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (entry_date, f"{entry_date}T12:00:00+00:00", f"{entry_date}T12:00:00+00:00", self.actor_id, self.actor_id, workspace_id),
            )
            entry_id = int(cursor.lastrowid)
            for provider_key, (total, used, left) in values.items():
                provider_id = conn.execute(
                    "SELECT id FROM providers WHERE provider_key = ?", (provider_key,)
                ).fetchone()["id"]
                conn.execute(
                    """INSERT INTO history_values(entry_id, provider_id, total_balance, used_balance, left_balance)
                       VALUES (?, ?, ?, ?, ?)""",
                    (entry_id, provider_id, total, used, left),
                )
            return entry_id

    def test_summary_uses_latest_balance_and_cumulative_spend_by_workspace(self) -> None:
        self.add_values(self.shared_id, "2030-01-01", {
            "openrouter": (100, 1, 99),
            "parallel": (50, 2, 48),
        })
        self.add_values(self.shared_id, "2030-01-02", {"openrouter": (120, 3, 117)})
        self.add_values(self.shared_id, "2030-01-02", {"openrouter": (125, 4, 121)})
        self.add_values(self.own_workspace_id, "2030-01-01", {
            "openrouter": (20, 5, 15),
            "firecrawl": (500, 10, 490),
        })

        response = self.client.get("/api/total-balances/summary")
        self.assertEqual(response.status_code, 200, response.text)
        summary = response.json()
        workspaces = {row["workspace_id"]: row for row in summary["workspaces"]}
        shared_values = {row["provider_key"]: row for row in workspaces[self.shared_id]["values"]}
        own_values = {row["provider_key"]: row for row in workspaces[self.own_workspace_id]["values"]}
        self.assertEqual(shared_values["openrouter"]["total_balance"], 125)
        self.assertEqual(shared_values["openrouter"]["left_balance"], 121)
        self.assertEqual(shared_values["openrouter"]["total_spent"], 8)
        self.assertEqual(shared_values["parallel"]["total_spent"], 2)
        self.assertEqual(own_values["firecrawl"]["unit"], "credits")
        self.assertEqual(own_values["firecrawl"]["total_spent"], 10)
        self.assertEqual(workspaces[self.other_workspace_id]["values"], [])

        totals = {row["provider_key"]: row for row in summary["team_totals"]}
        self.assertEqual(totals["openrouter"]["total_balance"], 145)
        self.assertEqual(totals["openrouter"]["left_balance"], 136)
        self.assertEqual(totals["openrouter"]["total_spent"], 13)
        self.assertEqual(totals["parallel"]["unit"], "USD")
        self.assertEqual(totals["firecrawl"]["unit"], "credits")

        for row in summary["workspaces"]:
            self.assertEqual(set(row), {"workspace_id", "workspace_kind", "label", "values"})
            for value in row["values"]:
                self.assertEqual(
                    set(value), {"provider_key", "display_name", "unit", "total_balance", "left_balance", "total_spent"}
                )
        self.assertNotIn("history", summary)
        self.assertNotIn("entry_date", response.text)
        self.assertNotIn("created_at", response.text)
        self.assertNotIn("entry_id", response.text)

    def test_admin_member_and_user_can_read_summary_without_history_escalation(self) -> None:
        self.add_values(self.shared_id, "2030-02-01", {"openrouter": (10, 1, 9)})
        self.add_values(self.own_workspace_id, "2030-02-02", {"openrouter": (20, 2, 18)})
        admin_summary = self.client.get("/api/total-balances/summary")
        self.assertEqual(admin_summary.status_code, 200, admin_summary.text)

        self.set_actor_role("member")
        member_summary = self.client.get("/api/total-balances/summary")
        self.assertEqual(member_summary.status_code, 200, member_summary.text)
        private_detail = self.client.get(f"/api/balances/overview?workspace_id={self.own_workspace_id}")
        self.assertEqual(private_detail.status_code, 403)

        self.set_actor_role("user")
        user_summary = self.client.get("/api/total-balances/summary")
        self.assertEqual(user_summary.status_code, 200, user_summary.text)
        other_detail = self.client.get(f"/api/balances/overview?workspace_id={self.other_workspace_id}")
        self.assertEqual(other_detail.status_code, 403)


if __name__ == "__main__":
    import unittest

    unittest.main()
