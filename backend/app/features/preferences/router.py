from __future__ import annotations

from fastapi import APIRouter, Depends

from ...core.database import db_connection
from ...core.dependencies import get_current_user
from ...core.permissions import require_capability
from .schemas import TimezoneBody
from .service import save_timezone

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.patch("/timezone")
def update_timezone(body: TimezoneBody, user: dict = Depends(get_current_user)):
    require_capability(user, "preferences:timezone:write")
    with db_connection() as conn:
        timezone_name = save_timezone(conn, int(user["id"]), body.timezone)
    return {"timezone": timezone_name}
