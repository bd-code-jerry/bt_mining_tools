from __future__ import annotations

from typing import Literal
from fastapi import APIRouter, Depends, Query
from ...core.database import db_connection
from ...core.dependencies import get_current_user
from ...core.permissions import require_capability
from .schemas import CategoryBody, CategoryPatch, CostBody, CreateCostBody, TransferBody, CreateTransferBody
from . import service

router = APIRouter(prefix='/api/expenses', tags=['expenses'])


def filters(
    q: str = Query(default='', max_length=200),
    category_id: int | None = Query(default=None, ge=1),
    period: Literal['all','day','week','month','custom'] = 'all',
    start_date: str | None = None,
    end_date: str | None = None,
):
    return {'q':q, 'category_id':category_id, 'period':period, 'start_date':start_date, 'end_date':end_date}


@router.get('/participants')
def participants(user: dict = Depends(get_current_user)):
    require_capability(user, 'expenses:read')
    with db_connection() as conn:
        return {'participants': service.participants(conn)}


@router.get('/categories')
def categories(user: dict = Depends(get_current_user)):
    require_capability(user, 'expenses:read')
    with db_connection() as conn:
        return {'categories':service.categories(conn)}


@router.post('/categories')
def create_category(body: CategoryBody, user: dict = Depends(get_current_user)):
    require_capability(user, 'expenses:write')
    with db_connection() as conn:
        return {'category':service.create_category(conn,user,body.model_dump())}


@router.patch('/categories/{category_id}')
def update_category(category_id: int, body: CategoryPatch, user: dict = Depends(get_current_user)):
    require_capability(user, 'expenses:manage')
    with db_connection() as conn:
        return {'category':service.update_category(conn,user,category_id,body.model_dump(exclude_unset=True))}


@router.get('/summary')
def summary(user: dict = Depends(get_current_user)):
    require_capability(user, 'expenses:read')
    with db_connection() as conn:
        return service.summary(conn)


@router.get('/people')
def people(criteria: dict = Depends(filters), user: dict = Depends(get_current_user)):
    require_capability(user, 'expenses:read')
    with db_connection() as conn:
        return service.people(conn,user,criteria)


@router.get('/costs')
def costs(
    participant_id: int | None = Query(default=None, ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    criteria: dict = Depends(filters), user: dict = Depends(get_current_user),
):
    require_capability(user, 'expenses:read')
    with db_connection() as conn:
        return service.costs(conn,user,criteria,participant_id=participant_id,page=page,page_size=page_size)


@router.post('/costs')
def create_cost(body: CreateCostBody, user: dict = Depends(get_current_user)):
    require_capability(user, 'expenses:write')
    with db_connection() as conn:
        return {'cost':service.save_cost(conn,user,body.model_dump())}


@router.put('/costs/{cost_id}')
def update_cost(cost_id: int, body: CostBody, user: dict = Depends(get_current_user)):
    require_capability(user, 'expenses:write')
    with db_connection() as conn:
        return {'cost':service.save_cost(conn,user,body.model_dump(),cost_id=cost_id)}


@router.delete('/costs/{cost_id}')
def delete_cost(cost_id: int, user: dict = Depends(get_current_user)):
    require_capability(user, 'expenses:write')
    with db_connection() as conn:
        service.delete_record(conn,user,'costs',cost_id)
    return {'ok':True}


@router.get('/transfers')
def transfers(
    kind: Literal['origin','received'] | None = None,
    page: int = Query(default=1, ge=1), page_size: int = Query(default=10, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    require_capability(user, 'expenses:read')
    with db_connection() as conn:
        return service.transfers(conn,user,kind=kind,page=page,page_size=page_size)


@router.post('/transfers')
def create_transfer(body: CreateTransferBody, user: dict = Depends(get_current_user)):
    require_capability(user, 'expenses:write')
    with db_connection() as conn:
        return {'transfer':service.save_transfer(conn,user,body.model_dump())}


@router.put('/transfers/{transfer_id}')
def update_transfer(transfer_id: int, body: TransferBody, user: dict = Depends(get_current_user)):
    require_capability(user, 'expenses:write')
    with db_connection() as conn:
        return {'transfer':service.save_transfer(conn,user,body.model_dump(),transfer_id=transfer_id)}


@router.delete('/transfers/{transfer_id}')
def delete_transfer(transfer_id: int, user: dict = Depends(get_current_user)):
    require_capability(user, 'expenses:write')
    with db_connection() as conn:
        service.delete_record(conn,user,'transfers',transfer_id)
    return {'ok':True}
