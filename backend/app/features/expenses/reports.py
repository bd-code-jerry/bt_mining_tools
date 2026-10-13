from __future__ import annotations

from fastapi import HTTPException
from . import categories, repository, validation


def can_edit(user: dict,row: dict) -> bool:
    return 'expenses:write' in user.get('capabilities',()) and (
        user['role']=='admin' or row['created_by']==user['id'])


def present_cost(conn,user: dict,row: dict) -> dict:
    return {key:row[key] for key in ('id','amount_cents','expense_date','category_id','category_path','note','created_by')} | {
        'allocated_cents':row.get('allocated_cents',row['amount_cents']),
        'can_edit':can_edit(user,row),'allocations':repository.allocations(conn,row['id'])}


def present_transfer(user: dict,row: dict) -> dict:
    return {key:row[key] for key in ('id','kind','amount_cents','transfer_date','note','created_by')} | {'can_edit':can_edit(user,row)}


def resolve_filters(conn,user: dict,criteria: dict,participant_id: int | None=None):
    repository.sync_participants(conn)
    start,end = validation.report_dates(criteria,user.get('timezone','UTC'))
    clauses,params = [],[]
    if criteria.get('category_id') is not None:
        ids = categories.descendant_ids(conn,criteria['category_id'])
        clauses.append('c.category_id IN ('+','.join('?' for _ in ids)+')')
        params.extend(ids)
    if start:
        clauses.append('c.expense_date>=?')
        params.append(start)
    if end:
        clauses.append('c.expense_date<=?')
        params.append(end)
    participants = repository.list_participants(conn)
    needle = (criteria.get('q') or '').strip().casefold()
    matched = [p for p in participants if not needle or needle in p['username'].casefold()]
    if participant_id is not None:
        if not any(p['id']==participant_id for p in participants):
            raise HTTPException(status_code=404,detail='Participant not found.')
        matched = [p for p in matched if p['id']==participant_id]
    matching_ids = [p['id'] for p in matched] if needle or participant_id is not None else None
    if matching_ids is not None:
        placeholders = ','.join('?' for _ in matching_ids) or 'NULL'
        clauses.append(f'EXISTS (SELECT 1 FROM expense_allocations a WHERE a.expense_id=c.id AND a.participant_id IN ({placeholders}))')
        params.extend(matching_ids)
    where = 'WHERE '+' AND '.join(clauses) if clauses else ''
    return where,params,matching_ids,matched,start,end


def people(conn,user: dict,criteria: dict) -> dict:
    where,params,_,matched,start,end = resolve_filters(conn,user,criteria)
    totals = repository.participant_totals(conn,where,params)
    historical = repository.historical_participant_ids(conn)
    rows = [{key:p[key] for key in ('id','username','role','status')} | {'total_cents':totals.get(p['id'],0)}
            for p in matched if p['eligible'] or p['id'] in historical]
    return {'people':rows,'total_cents':sum(row['total_cents'] for row in rows),'start_date':start,'end_date':end}


def costs(conn,user: dict,criteria: dict,*,participant_id: int | None=None,page: int=1,page_size: int=10) -> dict:
    where,params,matching_ids,_,start,end = resolve_filters(conn,user,criteria,participant_id)
    total_items,total = repository.cost_count_total(conn,where,params,matching_ids)
    info = validation.pagination(total_items,page,page_size)
    rows = repository.cost_rows(conn,where,params,matching_ids=matching_ids,page=info)
    return {'costs':[present_cost(conn,user,row) for row in rows], 'pagination':info,
            'filtered_total_cents':total,'start_date':start,'end_date':end}


def transfers(conn,user: dict,*,kind: str | None=None,page: int=1,page_size: int=10) -> dict:
    rows,info = repository.transfer_page(conn,kind,page,page_size,validation.pagination)
    return {'transfers':[present_transfer(user,row) for row in rows],'pagination':info}
