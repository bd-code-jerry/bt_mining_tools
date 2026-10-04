from __future__ import annotations

import sqlite3

from fastapi import HTTPException, status

from . import repository


def resolve_workspace(
    conn: sqlite3.Connection,
    user: dict,
    requested_workspace_id: int | None,
    *,
    write: bool = False,
) -> dict:
    role = user.get("role")
    if role not in {"admin", "member", "user"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unknown account role.")

    if role == "admin":
        workspace = (
            repository.get_workspace(conn, requested_workspace_id)
            if requested_workspace_id is not None
            else repository.get_shared_workspace(conn)
        )
        if workspace is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
        return workspace

    if role == "member":
        if write:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Members can view balances but cannot change them.",
            )
        workspace = repository.get_shared_workspace(conn)
        if workspace is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared workspace not found.")
        if requested_workspace_id is not None and requested_workspace_id != int(workspace["id"]):
            requested = repository.get_workspace(conn, requested_workspace_id)
            if requested is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this workspace.")
        return workspace

    try:
        own_workspace = repository.ensure_private_workspace(conn, int(user["id"]))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace owner not found.") from exc
    if requested_workspace_id is not None and requested_workspace_id != int(own_workspace["id"]):
        requested = repository.get_workspace(conn, requested_workspace_id)
        if requested is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this workspace.")
    return own_workspace


def accessible_workspaces(conn: sqlite3.Connection, user: dict) -> list[dict]:
    role = user.get("role")
    if role == "admin":
        return repository.list_workspaces(conn)
    if role == "member":
        workspace = repository.get_shared_workspace(conn)
        return [workspace] if workspace else []
    if role == "user":
        try:
            return [repository.ensure_private_workspace(conn, int(user["id"]))]
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace owner not found.") from exc
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unknown account role.")
