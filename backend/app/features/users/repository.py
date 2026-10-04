from __future__ import annotations

import sqlite3


def get_user(conn: sqlite3.Connection, user_id: int) -> dict | None:
    row = conn.execute(
        """SELECT id, username, email, role, status, created_at, last_login_at, timezone
           FROM users WHERE id = ?""",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def list_users(conn: sqlite3.Connection, status_filter: str | None = None) -> list[dict]:
    if status_filter is None:
        rows = conn.execute(
            """SELECT id, username, email, role, status, created_at, last_login_at, timezone
               FROM users ORDER BY created_at, id"""
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT id, username, email, role, status, created_at, last_login_at, timezone
               FROM users WHERE status = ? ORDER BY created_at, id""",
            (status_filter,),
        ).fetchall()
    return [dict(row) for row in rows]


def identifier_in_use(conn: sqlite3.Connection, username: str, email: str) -> bool:
    return conn.execute(
        """SELECT 1 FROM users WHERE username = ? COLLATE NOCASE
           OR (email IS NOT NULL AND email = ? COLLATE NOCASE) LIMIT 1""",
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
) -> int:
    cursor = conn.execute(
        """INSERT INTO users(username, email, password_hash, created_at, role, status)
           VALUES (?, ?, ?, ?, ?, 'active')""",
        (username, email, password_hash, created_at, role),
    )
    return int(cursor.lastrowid)


def set_role(conn: sqlite3.Connection, user_id: int, role: str) -> None:
    conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))


def set_status(conn: sqlite3.Connection, user_id: int, account_status: str) -> None:
    conn.execute("UPDATE users SET status = ? WHERE id = ?", (account_status, user_id))


def active_admin_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND status = 'active'").fetchone()[0])


def revoke_user_sessions(conn: sqlite3.Connection, user_id: int) -> int:
    cursor = conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    return int(cursor.rowcount)


def session_exists(conn: sqlite3.Connection, session_id: int) -> bool:
    return conn.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone() is not None


def delete_session(conn: sqlite3.Connection, session_id: int) -> bool:
    return conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,)).rowcount > 0


def list_sessions(conn: sqlite3.Connection, user_id: int, now: int) -> list[dict]:
    rows = conn.execute(
        """SELECT id, created_at, last_activity_at, expires_at FROM sessions
           WHERE user_id = ? AND expires_at > ? ORDER BY created_at DESC, id DESC""",
        (user_id, now),
    ).fetchall()
    return [dict(row) for row in rows]


def set_registration_enabled(conn: sqlite3.Connection, enabled: bool) -> None:
    conn.execute(
        """INSERT INTO app_settings(key, value) VALUES ('registration_enabled', ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
        ("true" if enabled else "false",),
    )


def registration_enabled(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT value FROM app_settings WHERE key = 'registration_enabled'").fetchone()
    return row is None or str(row[0]).strip().lower() in {"1", "true", "yes", "on"}


def set_email(conn: sqlite3.Connection, user_id: int, email: str | None) -> None:
    conn.execute("UPDATE users SET email = ? WHERE id = ?", (email, user_id))


def fetch_login_events(
    conn: sqlite3.Connection,
    *,
    lower_utc: str | None,
    upper_utc: str | None,
    account_id: int | None,
    role: str | None,
    limit: int = 500,
) -> list[dict]:
    clauses: list[str] = []
    parameters: list[object] = []
    if lower_utc is not None:
        clauses.append("le.signed_in_at >= ?")
        parameters.append(lower_utc)
    if upper_utc is not None:
        clauses.append("le.signed_in_at < ?")
        parameters.append(upper_utc)
    if account_id is not None:
        clauses.append("le.user_id = ?")
        parameters.append(account_id)
    if role is not None:
        clauses.append("le.role = ?")
        parameters.append(role)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    rows = conn.execute(
        """SELECT le.id, le.user_id, u.username, u.email, le.role, le.signed_in_at
           FROM login_events le JOIN users u ON u.id = le.user_id"""
        + where
        + " ORDER BY le.signed_in_at DESC, le.id DESC LIMIT ?",
        (*parameters, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_login_timestamps(
    conn: sqlite3.Connection,
    *,
    lower_utc: str,
    upper_utc: str,
    account_id: int | None,
    role: str | None,
) -> list[str]:
    clauses = ["signed_in_at >= ?", "signed_in_at < ?"]
    parameters: list[object] = [lower_utc, upper_utc]
    if account_id is not None:
        clauses.append("user_id = ?")
        parameters.append(account_id)
    if role is not None:
        clauses.append("role = ?")
        parameters.append(role)
    rows = conn.execute(
        "SELECT signed_in_at FROM login_events WHERE " + " AND ".join(clauses),
        parameters,
    ).fetchall()
    return [str(row[0]) for row in rows]
