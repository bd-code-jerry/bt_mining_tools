from __future__ import annotations

import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from . import repository

SUPPORTED_TIMEZONES = frozenset({"UTC", "America/New_York"})


def zone_for(value: str) -> ZoneInfo:
    if value not in SUPPORTED_TIMEZONES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose UTC or Eastern Time (ET).")
    return ZoneInfo(value)


def to_local_timestamp(value: str | None, timezone_name: str) -> str | None:
    if value is None:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(zone_for(timezone_name)).isoformat(timespec="seconds")


def local_date_utc_bounds(start_date: date, end_date: date, timezone_name: str) -> tuple[str, str]:
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="End date must be on or after start date.")
    if (end_date - start_date).days > 366:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 367 days.")
    zone = zone_for(timezone_name)
    lower = datetime.combine(start_date, time.min, tzinfo=zone).astimezone(timezone.utc)
    upper = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=zone).astimezone(timezone.utc)
    return lower.isoformat(timespec="seconds"), upper.isoformat(timespec="seconds")


def optional_local_date_utc_bounds(
    start_date: date | None,
    end_date: date | None,
    timezone_name: str,
) -> tuple[str | None, str | None]:
    if start_date is not None and end_date is not None:
        if end_date < start_date:
            raise HTTPException(status_code=422, detail="End date must be on or after start date.")
        if (end_date - start_date).days > 366:
            raise HTTPException(status_code=422, detail="Date range cannot exceed 367 days.")
    zone = zone_for(timezone_name)
    lower = (
        datetime.combine(start_date, time.min, tzinfo=zone).astimezone(timezone.utc).isoformat(timespec="seconds")
        if start_date is not None
        else None
    )
    upper = (
        datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=zone)
        .astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        if end_date is not None
        else None
    )
    return lower, upper


def save_timezone(conn: sqlite3.Connection, user_id: int, timezone_name: str) -> str:
    zone_for(timezone_name)
    conn.execute("BEGIN IMMEDIATE")
    if repository.get_timezone(conn, user_id) is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    repository.set_timezone(conn, user_id, timezone_name)
    return timezone_name
