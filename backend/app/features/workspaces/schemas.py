from __future__ import annotations

from pydantic import BaseModel


class WorkspaceSummary(BaseModel):
    id: int
    kind: str
    display_name: str
    owner_user_id: int | None
