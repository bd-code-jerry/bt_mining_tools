from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from ...core.database import db_connection
from ...core.dependencies import get_current_user
from ...core.permissions import require_capability
from ..workspaces.service import resolve_workspace
from .schemas import UsagePeriod
from .service import usage_summary_for_range

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("/summary")
def get_usage_summary(
    period: UsagePeriod = Query(default="all"),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    workspace_id: int | None = Query(default=None, ge=1),
    user: dict = Depends(get_current_user),
):
    require_capability(user, "usage:read")
    with db_connection() as conn:
        workspace = resolve_workspace(conn, user, workspace_id)
        return usage_summary_for_range(
            conn,
            workspace_id=int(workspace["id"]),
            period=period,
            start_date=start_date,
            end_date=end_date,
        )
