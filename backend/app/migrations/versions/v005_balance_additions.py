from __future__ import annotations

import sqlite3

VERSION = 5
NAME = 'balance_additions'


def apply(conn: sqlite3.Connection, *, initial_admin_username: str | None = None) -> None:
    # Old snapshots have no trustworthy top-up provenance. Keep them unclassified.
    conn.execute("ALTER TABLE history_entries ADD COLUMN entry_kind TEXT NOT NULL DEFAULT 'legacy' CHECK (entry_kind IN ('legacy', 'balance', 'topup'))")
    conn.execute('ALTER TABLE history_values ADD COLUMN added_balance REAL CHECK (added_balance IS NULL OR added_balance >= 0)')
    conn.execute('ALTER TABLE history_values ADD COLUMN balance_before REAL CHECK (balance_before IS NULL OR balance_before >= 0)')
    conn.execute('CREATE INDEX idx_history_entries_workspace_kind_date ON history_entries(workspace_id, entry_kind, entry_date DESC, id DESC)')
