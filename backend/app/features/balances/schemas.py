from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ProviderValue(BaseModel):
    total: float | None = Field(default=None, ge=0)
    used: float | None = Field(default=None, ge=0)
    left: float | None = Field(default=None, ge=0)


class HistoryBody(BaseModel):
    entry_date: date | None = None
    values: dict[str, ProviderValue] = Field(default_factory=dict)


class CreateHistoryBody(HistoryBody):
    expected_latest_entry_id: int | None


class AddBalanceBody(BaseModel):
    entry_date: date | None = None
    additions: dict[str, float] = Field(default_factory=dict)
