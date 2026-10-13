from __future__ import annotations

from fastapi import HTTPException
from ...core.database import utc_now_iso
from . import categories as category_service, reports, repository, validation


def participants(conn) -> list[dict]:
    repository.sync_participants(conn)
    return repository.list_participants(conn)


categories = category_service.catalog
create_category = category_service.create
update_category = category_service.update
summary = repository.summary
people = reports.people
costs = reports.costs
transfers = reports.transfers


def require_owned(conn,user: dict,kind: str,record_id: int) -> dict:
    row = repository.get_record(conn,kind,record_id)
    if row is None:
        raise HTTPException(status_code=404,detail='Ledger record not found.')
    if not reports.can_edit(user,row):
        raise HTTPException(status_code=403,detail='You may only correct your own ledger records.')
    return row


def deduplicated(conn,user: dict,kind: str,request_id: str,payload: str) -> dict | None:
    row = repository.retry_record(conn,kind,user['id'],request_id)
    if row and row['request_payload'] != payload:
        raise HTTPException(status_code=409,detail='This request identifier was already used with different financial fields.')
    return row


def save_cost(conn,user: dict,payload: dict,*,cost_id: int | None=None) -> dict:
    conn.execute('BEGIN IMMEDIATE')
    existing = require_owned(conn,user,'costs',cost_id) if cost_id is not None else None
    normalized = {'amount_cents':validation.money(payload['amount']),
        'expense_date':validation.calendar_date(payload['expense_date'],'Expense date'),
        'category_id':payload['category_id'],'note':payload.get('note',''),
        'participant_ids':validation.participant_ids(payload['participant_ids'])}
    encoded = validation.fingerprint(normalized)
    if existing is None:
        request_id = validation.request_identifier(payload.get('request_id'))
        retry = deduplicated(conn,user,'costs',request_id,encoded)
        if retry:
            return reports.present_cost(conn,user,retry)
    repository.sync_participants(conn)
    eligible = {p['id'] for p in repository.list_participants(conn) if p['eligible']}
    old_participants = {a['participant_id'] for a in repository.allocations(conn,cost_id)} if existing else set()
    if any(p not in eligible and p not in old_participants for p in normalized['participant_ids']):
        raise HTTPException(status_code=422,detail='Select active registered accounts; one or more participants are not eligible.')
    same_category = existing is not None and normalized['category_id']==existing['category_id']
    category = category_service.require_category(conn,normalized['category_id'],active=not same_category)
    values = {key:value for key,value in normalized.items() if key != 'participant_ids'}
    values['category_path'] = existing['category_path'] if same_category else category['path']
    now = utc_now_iso()
    values['updated_at'] = now
    if existing:
        repository.update_record(conn,'costs',cost_id,values)
    else:
        values.update(created_by=user['id'],request_actor_id=user['id'],request_id=request_id,
                      request_payload=encoded,created_at=now)
        cost_id = repository.insert_record(conn,'costs',values)
    repository.replace_allocations(conn,cost_id,validation.equal_shares(normalized['amount_cents'],normalized['participant_ids']))
    return reports.present_cost(conn,user,repository.get_record(conn,'costs',cost_id))


def save_transfer(conn,user: dict,payload: dict,*,transfer_id: int | None=None) -> dict:
    conn.execute('BEGIN IMMEDIATE')
    existing = require_owned(conn,user,'transfers',transfer_id) if transfer_id is not None else None
    if payload['kind'] not in {'origin','received'}:
        raise HTTPException(status_code=422,detail='Choose origin or received.')
    normalized = {'kind':payload['kind'],'amount_cents':validation.money(payload['amount']),
                  'transfer_date':validation.calendar_date(payload['transfer_date'],'Transfer date'),
                  'note':payload.get('note','')}
    encoded = validation.fingerprint(normalized)
    if existing is None:
        request_id = validation.request_identifier(payload.get('request_id'))
        retry = deduplicated(conn,user,'transfers',request_id,encoded)
        if retry:
            return reports.present_transfer(user,retry)
    now = utc_now_iso()
    values = {**normalized,'updated_at':now}
    if existing:
        repository.update_record(conn,'transfers',transfer_id,values)
    else:
        values.update(created_by=user['id'],request_actor_id=user['id'],request_id=request_id,
                      request_payload=encoded,created_at=now)
        transfer_id = repository.insert_record(conn,'transfers',values)
    return reports.present_transfer(user,repository.get_record(conn,'transfers',transfer_id))


def delete_record(conn,user: dict,kind: str,record_id: int) -> None:
    conn.execute('BEGIN IMMEDIATE')
    require_owned(conn,user,kind,record_id)
    conn.execute(f'DELETE FROM expense_{kind} WHERE id=?',(record_id,))
