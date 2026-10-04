from __future__ import annotations

import sqlite3


def workspace_aggregates(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """WITH ranked_history AS (
               SELECT he.workspace_id, hv.provider_id, hv.total_balance, hv.left_balance,
                      ROW_NUMBER() OVER (
                          PARTITION BY he.workspace_id, hv.provider_id
                          ORDER BY he.entry_date DESC, he.id DESC
                      ) AS row_number
               FROM history_entries he
               JOIN history_values hv ON hv.entry_id = he.id
           ), usage_totals AS (
               SELECT he.workspace_id, hv.provider_id, SUM(hv.used_balance) AS total_spent
               FROM history_entries he
               JOIN history_values hv ON hv.entry_id = he.id
               GROUP BY he.workspace_id, hv.provider_id
           )
           SELECT rh.workspace_id, p.provider_key, p.display_name, p.unit,
                  rh.total_balance, rh.left_balance, COALESCE(ut.total_spent, 0) AS total_spent
           FROM ranked_history rh
           JOIN usage_totals ut ON ut.workspace_id = rh.workspace_id AND ut.provider_id = rh.provider_id
           JOIN providers p ON p.id = rh.provider_id
           WHERE rh.row_number = 1
           ORDER BY p.sort_order, rh.workspace_id"""
    ).fetchall()
    return [dict(row) for row in rows]
