from __future__ import annotations

from fastapi import APIRouter, Depends

from ...core.database import db_connection
from ...core.dependencies import get_current_user
from ...core.permissions import require_capability
from .schemas import TotalBalanceSummary
from .service import get_total_balance_summary

router = APIRouter(prefix="/api/total-balances", tags=["total-balances"])


@router.get("/summary", response_model=TotalBalanceSummary)
def get_summary(user: dict = Depends(get_current_user)):
    require_capability(user, "total_balances:read")
    with db_connection() as conn:
        return get_total_balance_summary(conn)
