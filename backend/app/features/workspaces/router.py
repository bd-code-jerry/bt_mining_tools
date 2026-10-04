from __future__ import annotations

from fastapi import APIRouter, Depends

from ...core.dependencies import get_current_user
from ...core.permissions import require_capability
from ...core.database import db_connection
from .service import accessible_workspaces

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.get("")
def get_workspaces(user: dict = Depends(get_current_user)):
    require_capability(user, "workspaces:read")
    with db_connection() as conn:
        return {"workspaces": accessible_workspaces(conn, user)}
