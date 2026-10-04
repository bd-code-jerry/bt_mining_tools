from __future__ import annotations

from backend.app.database import db_connection
from tests.support import AuthenticatedWorkspaceTestCase


class UsageScopingTests(AuthenticatedWorkspaceTestCase):
    def test_usage_and_history_are_workspace_scoped(self) -> None:
        self.add_history(self.shared_id, "2025-01-01", used=5.0, left=15.0)
        self.add_history(self.own_workspace_id, "2025-01-02", used=2.0, left=18.0)
        self.add_history(self.other_workspace_id, "2025-01-03", used=9.0, left=11.0)
        self.set_actor_role("user")

        usage = self.client.get(
            f"/api/usage/summary?period=all&workspace_id={self.own_workspace_id}"
        )
        self.assertEqual(usage.status_code, 200, usage.text)
        self.assertEqual(usage.json()["entry_count"], 1)
        openrouter = next(row for row in usage.json()["by_provider"] if row["provider_key"] == "openrouter")
        self.assertEqual(openrouter["total_used"], 2.0)

        history = self.client.get(
            f"/api/balances/overview?workspace_id={self.own_workspace_id}"
        )
        self.assertEqual(history.status_code, 200)
        self.assertEqual([entry["entry_date"] for entry in history.json()["history"]], ["2025-01-02"])

        with db_connection() as conn:
            shared_count = conn.execute(
                "SELECT COUNT(*) FROM history_entries WHERE workspace_id = ?", (self.shared_id,)
            ).fetchone()[0]
        self.assertEqual(shared_count, 1)


if __name__ == "__main__":
    import unittest

    unittest.main()
