from __future__ import annotations

from pydantic import BaseModel


class ProviderTotal(BaseModel):
    provider_key: str
    display_name: str
    unit: str
    total_balance: float
    left_balance: float
    total_spent: float


class WorkspaceTotal(BaseModel):
    workspace_id: int
    workspace_kind: str
    label: str
    values: list[ProviderTotal]


class TotalBalanceSummary(BaseModel):
    workspaces: list[WorkspaceTotal]
    team_totals: list[ProviderTotal]
