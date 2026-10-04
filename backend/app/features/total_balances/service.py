from __future__ import annotations

import sqlite3

from ..workspaces.repository import list_workspaces
from . import repository


def get_total_balance_summary(conn: sqlite3.Connection) -> dict:
    workspaces = [
        {
            "workspace_id": int(workspace["id"]),
            "workspace_kind": str(workspace["kind"]),
            "label": str(workspace["display_name"]),
            "values": [],
        }
        for workspace in list_workspaces(conn)
    ]
    workspace_by_id = {row["workspace_id"]: row for row in workspaces}
    totals_by_provider: dict[str, dict] = {}
    for row in repository.workspace_aggregates(conn):
        workspace_id = int(row["workspace_id"])
        provider_key = str(row["provider_key"])
        values = {
            "provider_key": provider_key,
            "display_name": str(row["display_name"]),
            "unit": str(row["unit"]),
            "total_balance": float(row["total_balance"]),
            "left_balance": float(row["left_balance"]),
            "total_spent": float(row["total_spent"]),
        }
        workspace = workspace_by_id.get(workspace_id)
        if workspace is None:
            continue
        workspace["values"].append(values)
        team_total = totals_by_provider.get(provider_key)
        if team_total is None:
            team_total = {
                "provider_key": provider_key,
                "display_name": values["display_name"],
                "unit": values["unit"],
                "total_balance": 0.0,
                "left_balance": 0.0,
                "total_spent": 0.0,
            }
            totals_by_provider[provider_key] = team_total
        team_total["total_balance"] += values["total_balance"]
        team_total["left_balance"] += values["left_balance"]
        team_total["total_spent"] += values["total_spent"]
    return {"workspaces": workspaces, "team_totals": list(totals_by_provider.values())}
