from __future__ import annotations

import unittest
from datetime import date, timedelta

from backend.app.database import db_connection
from tests.support import AuthenticatedWorkspaceTestCase


class LoginActivityTests(AuthenticatedWorkspaceTestCase):
    def test_start_only_date_filter_uses_the_same_range_for_events_and_daily_counts(self) -> None:
        today = date.today()
        start = today - timedelta(days=2)
        with db_connection() as conn:
            conn.executemany(
                "INSERT INTO login_events(user_id, signed_in_at, role) VALUES (?, ?, ?)",
                [
                    (self.actor_id, f"{start + timedelta(days=offset)}T12:00:00+00:00", "member")
                    for offset in range(3)
                ],
            )

        params = {"start_date": start.isoformat(), "role": "member"}
        events = self.client.get("/api/users/login-events", params=params)
        daily = self.client.get("/api/users/login-events/daily", params=params)

        self.assertEqual(events.status_code, 200, events.text)
        self.assertEqual(daily.status_code, 200, daily.text)
        self.assertEqual(len(events.json()["events"]), 3)
        self.assertEqual(daily.json()["days"][0]["date"], start.isoformat())
        self.assertEqual(daily.json()["days"][-1]["date"], today.isoformat())
        self.assertEqual(sum(day["count"] for day in daily.json()["days"]), 3)

    def test_end_only_date_filter_uses_a_matching_thirty_day_range(self) -> None:
        end = date.today() - timedelta(days=2)
        included = end.isoformat() + "T12:00:00+00:00"
        excluded = (end + timedelta(days=1)).isoformat() + "T12:00:00+00:00"
        with db_connection() as conn:
            conn.executemany(
                "INSERT INTO login_events(user_id, signed_in_at, role) VALUES (?, ?, ?)",
                [
                    (self.actor_id, (end - timedelta(days=40)).isoformat() + "T12:00:00+00:00", "user"),
                    (self.actor_id, included, "user"),
                    (self.actor_id, excluded, "user"),
                ],
            )

        params = {"end_date": end.isoformat(), "role": "user"}
        events = self.client.get("/api/users/login-events", params=params)
        daily = self.client.get("/api/users/login-events/daily", params=params)

        self.assertEqual(events.status_code, 200, events.text)
        self.assertEqual(daily.status_code, 200, daily.text)
        self.assertEqual([event["signed_in_at"][:10] for event in events.json()["events"]], [end.isoformat()])
        self.assertEqual(daily.json()["days"][0]["date"], (end - timedelta(days=29)).isoformat())
        self.assertEqual(daily.json()["days"][-1]["date"], end.isoformat())
        self.assertEqual(sum(day["count"] for day in daily.json()["days"]), 1)

    def test_login_daily_buckets_follow_viewer_timezone(self) -> None:
        self.client.patch("/api/preferences/timezone", json={"timezone": "America/New_York"})
        with db_connection() as conn:
            conn.executemany(
                "INSERT INTO login_events(user_id, signed_in_at, role) VALUES (?, ?, ?)",
                [
                    (self.actor_id, "2030-01-02T01:30:00+00:00", "member"),
                    (self.actor_id, "2030-01-02T04:59:00+00:00", "member"),
                    (self.actor_id, "2030-01-02T05:00:00+00:00", "member"),
                ],
            )
        daily = self.client.get(
            "/api/users/login-events/daily",
            params={"start_date": "2030-01-01", "end_date": "2030-01-02"},
        )
        self.assertEqual(daily.status_code, 200, daily.text)
        self.assertEqual(daily.json()["timezone"], "America/New_York")
        self.assertEqual(daily.json()["days"], [{"date": "2030-01-01", "count": 2}, {"date": "2030-01-02", "count": 1}])
        events = self.client.get(
            "/api/users/login-events",
            params={"start_date": "2030-01-01", "end_date": "2030-01-01"},
        )
        self.assertEqual(events.status_code, 200, events.text)
        self.assertEqual(len(events.json()["events"]), 2)
        self.assertTrue(all("-05:00" in item["signed_in_at"] for item in events.json()["events"]))

    def test_et_timezone_handles_dst_transition(self) -> None:
        self.client.patch("/api/preferences/timezone", json={"timezone": "America/New_York"})
        with db_connection() as conn:
            conn.executemany(
                "INSERT INTO login_events(user_id, signed_in_at, role) VALUES (?, ?, ?)",
                [
                    (self.actor_id, "2024-03-10T06:59:00+00:00", "admin"),
                    (self.actor_id, "2024-03-10T07:01:00+00:00", "admin"),
                ],
            )
        events = self.client.get(
            "/api/users/login-events",
            params={"start_date": "2024-03-10", "end_date": "2024-03-10", "account_id": self.actor_id},
        )
        self.assertEqual(events.status_code, 200, events.text)
        timestamps = [item["signed_in_at"] for item in events.json()["events"]]
        self.assertIn("2024-03-10T01:59:00-05:00", timestamps)
        self.assertIn("2024-03-10T03:01:00-04:00", timestamps)
        daily = self.client.get(
            "/api/users/login-events/daily",
            params={"start_date": "2024-03-10", "end_date": "2024-03-10"},
        )
        self.assertEqual(daily.status_code, 200, daily.text)
        self.assertEqual(daily.json()["days"], [{"date": "2024-03-10", "count": 2}])


if __name__ == "__main__":
    unittest.main()
