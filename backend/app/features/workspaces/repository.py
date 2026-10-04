from __future__ import annotations

import sqlite3


def get_workspace(conn: sqlite3.Connection, workspace_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, kind, owner_user_id, display_name, created_at FROM workspaces WHERE id = ?",
        (workspace_id,),
    ).fetchone()
    return dict(row) if row else None


def get_shared_workspace(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        "SELECT id, kind, owner_user_id, display_name, created_at FROM workspaces WHERE kind = 'shared'"
    ).fetchone()
    return dict(row) if row else None


def get_private_workspace(conn: sqlite3.Connection, owner_user_id: int) -> dict | None:
    row = conn.execute(
        """SELECT id, kind, owner_user_id, display_name, created_at FROM workspaces
           WHERE kind = 'private' AND owner_user_id = ?""",
        (owner_user_id,),
    ).fetchone()
    return dict(row) if row else None


def list_workspaces(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT id, kind, owner_user_id, display_name, created_at FROM workspaces
           ORDER BY CASE kind WHEN 'shared' THEN 0 ELSE 1 END, display_name COLLATE NOCASE, id"""
    ).fetchall()
    return [dict(row) for row in rows]


def ensure_private_workspace(conn: sqlite3.Connection, owner_user_id: int) -> dict:
    workspace = get_private_workspace(conn, owner_user_id)
    if workspace:
        return workspace
    user = conn.execute("SELECT username FROM users WHERE id = ?", (owner_user_id,)).fetchone()
    if user is None:
        raise ValueError("Cannot create a workspace for a missing account.")
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    workspace = get_private_workspace(conn, owner_user_id)
    if workspace:
        return workspace
    cursor = conn.execute(
        """INSERT INTO workspaces(kind, owner_user_id, display_name, created_at)
           VALUES ('private', ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))""",
        (owner_user_id, f"{user['username']}'s workspace"),
    )
    return get_workspace(conn, int(cursor.lastrowid))
