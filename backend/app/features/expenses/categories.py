from __future__ import annotations

import sqlite3
from fastapi import HTTPException
from ...core.database import utc_now_iso
from . import repository


def catalog(conn) -> list[dict]:
    rows = repository.list_categories(conn)
    by_id = {row['id']:row for row in rows}
    historical = repository.historical_category_paths(conn)
    output = []
    for row in rows:
        chain = []
        current = row
        seen = set()
        while current is not None:
            if current['id'] in seen:
                raise HTTPException(status_code=409,detail='Category tree contains a cycle.')
            seen.add(current['id'])
            chain.append(current)
            current = by_id.get(current['parent_id'])
        output.append({**row,'archived':bool(row['archived']),
            'effective_archived':any(item['archived'] for item in chain),
            'path':' / '.join(item['name'] for item in reversed(chain)),
            'historical_paths':historical.get(row['id'],[])})
    return output


def require_category(conn,category_id: int,*,active: bool=False) -> dict:
    category = next((row for row in catalog(conn) if row['id']==category_id),None)
    if category is None:
        raise HTTPException(status_code=422,detail='Category does not exist.')
    if active and category['effective_archived']:
        raise HTTPException(status_code=422,detail='Archived categories cannot be selected for new costs.')
    return category


def descendant_ids(conn,category_id: int) -> list[int]:
    rows = catalog(conn)
    if not any(row['id']==category_id for row in rows):
        raise HTTPException(status_code=422,detail='Category does not exist.')
    children = {}
    for row in rows:
        children.setdefault(row['parent_id'],[]).append(row['id'])
    result = [category_id]
    for item in result:
        result.extend(children.get(item,[]))
    return result


def validate_name(conn,name: str,parent_id: int | None,exclude_id: int | None=None) -> str:
    if not isinstance(name,str) or not name.strip():
        raise HTTPException(status_code=422,detail='Category name is required.')
    name = name.strip()
    for row in repository.list_categories(conn):
        if row['id'] != exclude_id and row['parent_id']==parent_id and row['name'].casefold()==name.casefold():
            raise HTTPException(status_code=409,detail='A category with that name already exists under this parent.')
    return name


def create(conn,user: dict,payload: dict) -> dict:
    conn.execute('BEGIN IMMEDIATE')
    parent_id = payload.get('parent_id')
    if parent_id is not None:
        require_category(conn,parent_id,active=True)
    name = validate_name(conn,payload['name'],parent_id)
    now = utc_now_iso()
    try:
        cursor = conn.execute('''INSERT INTO expense_categories(name,parent_id,created_by,created_at,updated_at)
            VALUES (?,?,?,?,?)''',(name,parent_id,user['id'],now,now))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409,detail='Category already exists.') from exc
    return require_category(conn,int(cursor.lastrowid))


def update(conn,user: dict,category_id: int,payload: dict) -> dict:
    conn.execute('BEGIN IMMEDIATE')
    existing = require_category(conn,category_id)
    parent_id = payload.get('parent_id',existing['parent_id'])
    if parent_id is not None:
        parent = require_category(conn,parent_id)
        if parent_id in descendant_ids(conn,category_id):
            raise HTTPException(status_code=422,detail='A category cannot be its own ancestor.')
        if parent_id != existing['parent_id'] and parent['effective_archived']:
            raise HTTPException(status_code=422,detail='Choose an active parent category.')
    name = validate_name(conn,payload.get('name',existing['name']),parent_id,category_id)
    archived = payload.get('archived',existing['archived'])
    if type(archived) is not bool:
        raise HTTPException(status_code=422,detail='Archived must be true or false.')
    conn.execute('UPDATE expense_categories SET name=?,parent_id=?,archived=?,updated_at=? WHERE id=?',
                 (name,parent_id,int(archived),utc_now_iso(),category_id))
    return require_category(conn,category_id)
