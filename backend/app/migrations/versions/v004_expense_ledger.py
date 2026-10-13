from __future__ import annotations

import sqlite3

VERSION = 4
NAME = 'expense_ledger'


def apply(conn: sqlite3.Connection, *, initial_admin_username: str | None = None) -> None:
    statements = [
        """CREATE TABLE expense_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""",
        """CREATE TABLE expense_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER REFERENCES expense_categories(id),
            archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        "CREATE UNIQUE INDEX idx_expense_category_roots ON expense_categories(name COLLATE NOCASE) WHERE parent_id IS NULL",
        "CREATE UNIQUE INDEX idx_expense_category_children ON expense_categories(parent_id,name COLLATE NOCASE) WHERE parent_id IS NOT NULL",
        """CREATE TABLE expense_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL CHECK(kind IN ('origin','received')),
            amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
            transfer_date TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            request_actor_id INTEGER NOT NULL,
            request_id TEXT NOT NULL,
            request_payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(request_actor_id,request_id)
        )""",
        "CREATE INDEX idx_expense_transfers_date ON expense_transfers(kind,transfer_date DESC,id DESC)",
        """CREATE TABLE expense_costs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
            expense_date TEXT NOT NULL,
            category_id INTEGER NOT NULL REFERENCES expense_categories(id),
            category_path TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            request_actor_id INTEGER NOT NULL,
            request_id TEXT NOT NULL,
            request_payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(request_actor_id,request_id)
        )""",
        "CREATE INDEX idx_expense_costs_date ON expense_costs(expense_date DESC,id DESC)",
        "CREATE INDEX idx_expense_costs_category ON expense_costs(category_id,expense_date)",
        """CREATE TABLE expense_allocations (
            expense_id INTEGER NOT NULL REFERENCES expense_costs(id) ON DELETE CASCADE,
            participant_id INTEGER NOT NULL REFERENCES expense_participants(id),
            share_cents INTEGER NOT NULL CHECK(share_cents >= 0),
            PRIMARY KEY(expense_id,participant_id)
        )""",
        "CREATE INDEX idx_expense_allocations_participant ON expense_allocations(participant_id,expense_id)",
        """INSERT INTO expense_participants(user_id,username,role,created_at)
            SELECT id,username,role,created_at FROM users ORDER BY id""",
        """CREATE TRIGGER expense_participant_account_updated AFTER UPDATE OF username,role ON users
            BEGIN UPDATE expense_participants SET username=NEW.username,role=NEW.role WHERE user_id=NEW.id; END""",
        """CREATE TRIGGER expense_participant_account_deleted BEFORE DELETE ON users
            BEGIN UPDATE expense_participants SET username=OLD.username,role=OLD.role WHERE user_id=OLD.id; END""",
    ]
    for statement in statements:
        conn.execute(statement)
