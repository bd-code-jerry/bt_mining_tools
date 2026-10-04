from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class TimezoneBody(BaseModel):
    timezone: Literal["UTC", "America/New_York"]
