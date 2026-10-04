from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query

from ...core.database import db_connection
from ...core.dependencies import get_current_user
from ...core.permissions import require_capability
from . import service
from .schemas import (
    ApproveUserBody,
    CreateUserBody,
    EmailBody,
    PasswordResetBody,
    RegistrationBody,
    RoleBody,
    StatusBody,
)

router = APIRouter(prefix="/api/users", tags=["users"])


def _admin(user: dict) -> None:
    require_capability(user, "users:manage")


@router.get("/login-events/daily")
def get_daily_login_events(
    start_date: date | None = None,
    end_date: date | None = None,
    account_id: int | None = Query(default=None, gt=0),
    role: Literal["admin", "member", "user"] | None = None,
    user: dict = Depends(get_current_user),
):
    _admin(user)
    with db_connection() as conn:
        days = service.daily_login_counts(
            conn,
            viewer_timezone=str(user["timezone"]),
            start_date=start_date,
            end_date=end_date,
            account_id=account_id,
            role=role,
        )
    return {"timezone": user["timezone"], "days": days}


@router.get("/login-events")
def get_login_events(
    start_date: date | None = None,
    end_date: date | None = None,
    account_id: int | None = Query(default=None, gt=0),
    role: Literal["admin", "member", "user"] | None = None,
    user: dict = Depends(get_current_user),
):
    _admin(user)
    with db_connection() as conn:
        events = service.login_events(
            conn,
            viewer_timezone=str(user["timezone"]),
            start_date=start_date,
            end_date=end_date,
            account_id=account_id,
            role=role,
        )
    return {"timezone": user["timezone"], "events": events}


@router.get("/pending")
def get_pending_accounts(user: dict = Depends(get_current_user)):
    _admin(user)
    with db_connection() as conn:
        accounts = service.list_accounts(conn, str(user["timezone"]), "pending")
    return {"users": accounts}


@router.get("/registration")
def get_registration(user: dict = Depends(get_current_user)):
    _admin(user)
    with db_connection() as conn:
        return {"registration_enabled": service.registration_state(conn)}


@router.patch("/registration")
def patch_registration(body: RegistrationBody, user: dict = Depends(get_current_user)):
    _admin(user)
    with db_connection() as conn:
        enabled = service.set_registration(conn, body.enabled)
    return {"registration_enabled": enabled}


@router.get("")
def get_accounts(
    status_filter: Literal["pending", "active", "disabled"] | None = Query(default=None, alias="status"),
    user: dict = Depends(get_current_user),
):
    _admin(user)
    with db_connection() as conn:
        accounts = service.list_accounts(conn, str(user["timezone"]), status_filter)
        registration_enabled = service.registration_state(conn)
    return {"users": accounts, "registration_enabled": registration_enabled}


@router.post("", status_code=201)
def post_account(body: CreateUserBody, user: dict = Depends(get_current_user)):
    _admin(user)
    with db_connection() as conn:
        account = service.create_account(
            conn,
            username=body.username,
            email=body.email,
            password=body.password,
            role=body.role,
        )
        account = service.present_account(account, str(user["timezone"]))
    return {"user": account}


@router.post("/pending/{user_id}/approve")
def approve_account(user_id: int, body: ApproveUserBody, user: dict = Depends(get_current_user)):
    _admin(user)
    with db_connection() as conn:
        account = service.approve_pending(conn, user_id, body.role)
        account = service.present_account(account, str(user["timezone"]))
    return {"user": account}


@router.delete("/pending/{user_id}")
def deny_account(user_id: int, user: dict = Depends(get_current_user)):
    _admin(user)
    with db_connection() as conn:
        service.deny_pending(conn, user_id)
    return {"ok": True}


@router.get("/{user_id}/sessions")
def get_sessions(user_id: int, user: dict = Depends(get_current_user)):
    _admin(user)
    with db_connection() as conn:
        sessions = service.active_sessions(conn, user_id, str(user["timezone"]))
    return {"sessions": sessions}


@router.delete("/{user_id}/sessions")
def delete_sessions(user_id: int, user: dict = Depends(get_current_user)):
    _admin(user)
    with db_connection() as conn:
        revoked = service.revoke_sessions(conn, user_id)
    return {"revoked": revoked}


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, user: dict = Depends(get_current_user)):
    _admin(user)
    with db_connection() as conn:
        service.revoke_session(conn, session_id)
    return {"ok": True}


@router.patch("/{user_id}/role")
def patch_role(user_id: int, body: RoleBody, user: dict = Depends(get_current_user)):
    _admin(user)
    with db_connection() as conn:
        account = service.change_role(conn, user_id, body.role)
        account = service.present_account(account, str(user["timezone"]))
    return {"user": account}


@router.patch("/{user_id}/status")
def patch_status(user_id: int, body: StatusBody, user: dict = Depends(get_current_user)):
    _admin(user)
    with db_connection() as conn:
        account = service.change_status(conn, user_id, body.status)
        account = service.present_account(account, str(user["timezone"]))
    return {"user": account}


@router.post("/{user_id}/password-reset")
def post_password_reset(user_id: int, body: PasswordResetBody, user: dict = Depends(get_current_user)):
    _admin(user)
    with db_connection() as conn:
        service.reset_password(conn, user_id, body.new_password)
    return {"ok": True}


@router.patch("/{user_id}")
def patch_account(user_id: int, body: EmailBody, user: dict = Depends(get_current_user)):
    _admin(user)
    with db_connection() as conn:
        account = service.update_email(conn, user_id, body.email)
        account = service.present_account(account, str(user["timezone"]))
    return {"user": account}


@router.delete("/{user_id}")
def delete_account(user_id: int, user: dict = Depends(get_current_user)):
    _admin(user)
    with db_connection() as conn:
        service.delete_account(conn, user_id)
    return {"ok": True}
