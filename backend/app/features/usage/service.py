from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import HTTPException, status

from . import repository
from .schemas import UsagePeriod


def _resolve_range(
    conn,
    *,
    workspace_id: int,
    period: UsagePeriod,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[str | None, str | None]:
    if period == "all":
        return repository.history_bounds(conn, workspace_id)
    if period == "custom":
        if start_date is None or end_date is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Custom range requires both start_date and end_date.",
            )
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Start date cannot be after end date.",
            )
        return start_date.isoformat(), end_date.isoformat()

    anchor = end_date or repository.latest_history_date(conn, workspace_id) or date.today()
    if period == "day":
        start = anchor
    elif period == "week":
        start = anchor - timedelta(days=6)
    elif period == "month":
        start = anchor - timedelta(days=29)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported usage period.",
        )
    return start.isoformat(), anchor.isoformat()


def usage_summary_for_range(
    conn,
    *,
    workspace_id: int,
    period: UsagePeriod = "all",
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    resolved_start, resolved_end = _resolve_range(
        conn,
        workspace_id=workspace_id,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )
    if period == "all":
        by_provider = repository.aggregate_all_time(conn, workspace_id)
    elif resolved_start is None or resolved_end is None:
        by_provider = repository.aggregate_all_time(conn, workspace_id)
    else:
        by_provider = repository.aggregate_range(conn, workspace_id, resolved_start, resolved_end)
    by_unit: dict[str, float] = {}
    for row in by_provider:
        unit = row["unit"]
        by_unit[unit] = by_unit.get(unit, 0.0) + float(row["total_used"] or 0.0)
    return {
        "period": period,
        "start_date": resolved_start,
        "end_date": resolved_end,
        "entry_count": repository.history_count(conn, workspace_id, resolved_start, resolved_end),
        "by_unit": by_unit,
        "by_provider": by_provider,
    }
