from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from math import ceil

from fastapi import HTTPException
from ..preferences.service import zone_for

MAX_CENTS = 9223372036854775807


def money(value: str) -> int:
    # Parsing the original string prevents floating-point rounding and silent precision loss.
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]{1,2})?', value.strip()):
        raise HTTPException(status_code=422, detail='Amount must be a positive decimal USD amount with at most two decimal places.')
    cents = int(Decimal(value.strip()) * 100)
    if cents <= 0 or cents > MAX_CENTS:
        raise HTTPException(status_code=422, detail='Amount must be positive and within the supported range.')
    return cents


def calendar_date(value: str, label: str) -> str:
    try:
        if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
            raise ValueError()
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f'{label} must be a valid ISO calendar date (YYYY-MM-DD).') from exc


def report_dates(criteria: dict, timezone_name: str) -> tuple[str | None,str | None]:
    period = criteria.get('period','all')
    if period == 'all':
        # Explicit bounds may be used by callers that do not use the period picker.
        start = calendar_date(criteria['start_date'],'Start date') if criteria.get('start_date') else None
        end = calendar_date(criteria['end_date'],'End date') if criteria.get('end_date') else None
    elif period in {'day','week','month'}:
        today = datetime.now(zone_for(timezone_name)).date()
        days = {'day':1,'week':7,'month':30}[period]
        start,end = (today-timedelta(days=days-1)).isoformat(),today.isoformat()
    elif period == 'custom':
        if not criteria.get('start_date') or not criteria.get('end_date'):
            raise HTTPException(status_code=422, detail='Custom range requires start and end dates.')
        start,end = calendar_date(criteria['start_date'],'Start date'),calendar_date(criteria['end_date'],'End date')
    else:
        raise HTTPException(status_code=422, detail='Choose all, day, week, month, or custom period.')
    if start and end and end < start:
        raise HTTPException(status_code=422, detail='End date must be on or after start date.')
    return start,end


def pagination(total: int, page: int, page_size: int) -> dict:
    size = max(1,min(int(page_size),100))
    pages = max(1,ceil(total/size))
    return {'page':max(1,min(int(page),pages)), 'page_size':size,'total_items':total,'total_pages':pages}


def fingerprint(payload: dict) -> str:
    return json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False)


def request_identifier(value: str | None) -> str:
    if not isinstance(value,str) or not value.strip():
        raise HTTPException(status_code=422,detail='A request identifier is required to save a new record.')
    return value.strip()


def participant_ids(values: list) -> list[int]:
    if not values or any(type(value) is not int or value <= 0 for value in values):
        raise HTTPException(status_code=422,detail='Select at least one valid participant.')
    if len(set(values)) != len(values):
        raise HTTPException(status_code=422,detail='Participants must be distinct.')
    return sorted(values)


def equal_shares(cents: int, ids: list[int]) -> list[tuple[int,int]]:
    base,remainder = divmod(cents,len(ids))
    return [(participant,base+(index < remainder)) for index,participant in enumerate(ids)]
