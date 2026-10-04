from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel

UsagePeriod = Literal["all", "day", "week", "month", "custom"]


class UsageFilters(BaseModel):
    period: UsagePeriod = "all"
    start_date: date | None = None
    end_date: date | None = None
    workspace_id: int | None = None
