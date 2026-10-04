from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from ...core.config import COOKIE_SECURE, SESSION_COOKIE_NAME, SESSION_DAYS
from ...core.dependencies import get_current_user
from ...core.database import db_connection
from ...core.security import hash_session_token
from .schemas import LoginBody, RegisterBody
from .service import authenticate, create_session, get_registration_state, register_account, safe_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _authenticated_response(conn, user: dict) -> JSONResponse:
    token, _expires_at = create_session(conn, int(user["id"]), str(user["role"]))
    response = JSONResponse({"user": safe_user(user)})
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/register")
def register(body: RegisterBody):
    with db_connection() as conn:
        user = register_account(
            conn,
            username=body.username,
            email=body.email,
            password=body.password,
            registration_code=body.registration_code,
        )
        if user["status"] == "pending":
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={
                    "status": "pending",
                    "message": "Your account request is waiting for admin approval.",
                    "user": safe_user(user),
                },
            )
        return _authenticated_response(conn, user)


@router.post("/login")
def login(body: LoginBody):
    identifier = (body.identifier or body.username or "").strip()
    if not identifier:
        raise HTTPException(status_code=422, detail="Enter your username or email address.")
    with db_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        user = authenticate(conn, identifier, body.password)
        return _authenticated_response(conn, user)


@router.post("/logout")
def logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        with db_connection() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_session_token(token),))
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    with db_connection() as conn:
        registration_state = get_registration_state(conn)
    return {"user": user, **registration_state}


@router.get("/registration-config")
def registration_config():
    with db_connection() as conn:
        return get_registration_state(conn)
