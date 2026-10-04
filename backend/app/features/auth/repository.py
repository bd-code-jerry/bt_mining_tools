from __future__ import annotations

import sqlite3


def count_users(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])


def registration_enabled(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = 'registration_enabled'"
    ).fetchone()
    return row is None or str(row[0]).strip().lower() in {"1", "true", "yes", "on"}


def identifier_in_use(conn: sqlite3.Connection, username: str, email: str) -> bool:
    return conn.execute(
        """SELECT 1 FROM users
           WHERE username = ? COLLATE NOCASE
              OR (email IS NOT NULL AND email = ? COLLATE NOCASE)
           LIMIT 1""",
        (username, email),
    ).fetchone() is not None


def insert_user(
    conn: sqlite3.Connection,
    *,
    username: str,
    email: str,
    password_hash: str,
    created_at: str,
    role: str,
    account_status: str,
) -> int:
    cursor = conn.execute(
        """INSERT INTO users(username, email, password_hash, created_at, role, status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (username, email, password_hash, created_at, role, account_status),
    )
    return int(cursor.lastrowid)


def get_user_for_login(conn: sqlite3.Connection, identifier: str) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT id, username, email, password_hash, role, status,
                  created_at, last_login_at, timezone
           FROM users
           WHERE username = ? COLLATE NOCASE
              OR (email IS NOT NULL AND email = ? COLLATE NOCASE)
           LIMIT 1""",
        (identifier, identifier),
    ).fetchone()


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, username, email, role, status, timezone FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def create_session_row(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    token_hash: str,
    created_at: str,
    expires_at: int,
) -> None:
    conn.execute(
        """INSERT INTO sessions(token_hash, user_id, created_at, expires_at, last_activity_at)
           VALUES (?, ?, ?, ?, ?)""",
        (token_hash, user_id, created_at, expires_at, created_at),
    )


def record_login_event(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    signed_in_at: str,
    role: str,
) -> None:
    conn.execute(
        "INSERT INTO login_events(user_id, signed_in_at, role) VALUES (?, ?, ?)",
        (user_id, signed_in_at, role),
    )
