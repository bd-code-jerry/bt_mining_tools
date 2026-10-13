from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from ...core.database import db_connection
from ...core.dependencies import get_current_user
from ...core.permissions import require_capability
from ..workspaces.service import resolve_workspace
from .schemas import AddBalanceBody, CreateHistoryBody, HistoryBody
from .service import (
    create_add_balance_entry,
    create_history_entry,
    delete_history_entry,
    get_history_entry,
    overview,
    update_history_entry,
    update_add_balance_entry,
)

router = APIRouter(prefix="/api/balances", tags=["balances"])


@router.get("/overview")
def get_overview(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=5, ge=1, le=100),
    topup_page: int = Query(default=1, ge=1),
    topup_page_size: int = Query(default=5, ge=1, le=100),
    workspace_id: int | None = Query(default=None, ge=1),
    user: dict = Depends(get_current_user),
):
    require_capability(user, "balances:read")
    with db_connection() as conn:
        workspace = resolve_workspace(conn, user, workspace_id)
        return overview(conn, workspace_id=int(workspace["id"]), page=page, page_size=page_size, topup_page=topup_page, topup_page_size=topup_page_size)


@router.get("/history/{entry_id}")
def get_entry(
    entry_id: int,
    workspace_id: int | None = Query(default=None, ge=1),
    user: dict = Depends(get_current_user),
):
    require_capability(user, "balances:read")
    with db_connection() as conn:
        workspace = resolve_workspace(conn, user, workspace_id)
        return get_history_entry(conn, entry_id, int(workspace["id"]))


@router.post("/history")
def create_entry(
    body: CreateHistoryBody,
    workspace_id: int | None = Query(default=None, ge=1),
    user: dict = Depends(get_current_user),
):
    require_capability(user, "balances:write")
    payload: dict[str, Any] = body.model_dump(mode="json")
    with db_connection() as conn:
        workspace = resolve_workspace(conn, user, workspace_id, write=True)
        entry = create_history_entry(conn, int(user["id"]), payload, workspace_id=int(workspace["id"]))
    return {"entry": entry}


@router.post("/add-balance")
def add_balance(
    body: AddBalanceBody,
    workspace_id: int | None = Query(default=None, ge=1),
    user: dict = Depends(get_current_user),
):
    require_capability(user, "balances:write")
    payload: dict[str, Any] = body.model_dump(mode="json")
    with db_connection() as conn:
        workspace = resolve_workspace(conn, user, workspace_id, write=True)
        entry = create_add_balance_entry(conn, int(user["id"]), payload, workspace_id=int(workspace["id"]))
    return {"entry": entry}


@router.put("/history/{entry_id}")
def update_entry(
    entry_id: int,
    body: HistoryBody,
    workspace_id: int | None = Query(default=None, ge=1),
    user: dict = Depends(get_current_user),
):
    require_capability(user, "balances:write")
    payload: dict[str, Any] = body.model_dump(mode="json")
    with db_connection() as conn:
        workspace = resolve_workspace(conn, user, workspace_id, write=True)
        entry = update_history_entry(
            conn,
            entry_id,
            int(user["id"]),
            payload,
            workspace_id=int(workspace["id"]),
        )
    return {"entry": entry}


@router.delete("/history/{entry_id}")
def delete_entry(
    entry_id: int,
    workspace_id: int | None = Query(default=None, ge=1),
    user: dict = Depends(get_current_user),
):
    require_capability(user, "balances:write")
    with db_connection() as conn:
        workspace = resolve_workspace(conn, user, workspace_id, write=True)
        delete_history_entry(conn, entry_id, int(workspace["id"]))
    return {"ok": True}


@router.put("/add-balance/{entry_id}")
def update_add_balance(entry_id: int, body: AddBalanceBody,
                       workspace_id: int | None = Query(default=None, ge=1),
                       user: dict = Depends(get_current_user)):
    require_capability(user, "balances:write")
    with db_connection() as conn:
        workspace = resolve_workspace(conn, user, workspace_id, write=True)
        entry = update_add_balance_entry(conn, entry_id, int(user["id"]), body.model_dump(mode="json"), workspace_id=int(workspace["id"]))
    return {"entry": entry}
