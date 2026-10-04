from __future__ import annotations

import sqlite3

from fastapi import HTTPException, status

from ...core import config
from ...core.permissions import capabilities_for_role
from ...core.security import (
    create_session_token,
    hash_password,
    hash_session_token,
    unix_now,
    utc_now_iso,
    validate_email,
    validate_password,
    validate_username,
    verify_password,
)
from . import repository


def _public_user(row: sqlite3.Row | dict) -> dict:
    role = str(row["role"])
    return {
        "id": int(row["id"]),
        "username": str(row["username"]),
        "email": row["email"],
        "role": role,
        "status": str(row["status"]),
        "timezone": str(row.get("timezone", "UTC")) if isinstance(row, dict) else str(row["timezone"]),
        "capabilities": capabilities_for_role(role),
    }


def register_account(
    conn: sqlite3.Connection,
    *,
    username: str,
    email: str,
    password: str,
    registration_code: str | None,
) -> dict:
    try:
        normalized_username = validate_username(username)
        normalized_email = validate_email(email)
        validate_password(password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if config.REGISTRATION_CODE and (registration_code or "").strip() != config.REGISTRATION_CODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The team registration code is incorrect.",
        )

    encoded_password = hash_password(password)
    conn.execute("BEGIN IMMEDIATE")
    if not repository.registration_enabled(conn):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Registration is currently closed.")
    if repository.identifier_in_use(conn, normalized_username, normalized_email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username or email address is already in use.",
        )

    first_account = repository.count_users(conn) == 0
    role = "admin" if first_account else "member"
    account_status = "active" if first_account else "pending"
    created_at = utc_now_iso()
    try:
        user_id = repository.insert_user(
            conn,
            username=normalized_username,
            email=normalized_email,
            password_hash=encoded_password,
            created_at=created_at,
            role=role,
            account_status=account_status,
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username or email address is already in use.",
        ) from exc

    return {
        "id": user_id,
        "username": normalized_username,
        "email": normalized_email,
        "role": role,
        "status": account_status,
        "timezone": "UTC",
        "capabilities": capabilities_for_role(role),
        "created_at": created_at,
        "last_login_at": None,
    }


def authenticate(conn: sqlite3.Connection, identifier: str, password: str) -> dict:
    row = repository.get_user_for_login(conn, identifier.strip())
    if row is None or not verify_password(password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username/email or password.")
    if row["status"] == "pending":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your account is waiting for admin approval.")
    if row["status"] != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is disabled.")
    return _public_user(row)


def create_session(
    conn: sqlite3.Connection,
    user_id: int,
    role: str,
) -> tuple[str, int]:
    user = repository.get_user_by_id(conn, user_id)
    if user is None or user["status"] != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is not active.")
    # Persisted account state is authoritative if a role changed since authentication.
    role = str(user["role"])

    token = create_session_token()
    now_unix = unix_now()
    expires_at = now_unix + config.SESSION_DAYS * 24 * 60 * 60
    now = utc_now_iso()
    conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now_unix,))
    repository.create_session_row(
        conn,
        user_id=user_id,
        token_hash=hash_session_token(token),
        created_at=now,
        expires_at=expires_at,
    )
    conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now, user_id))
    repository.record_login_event(conn, user_id=user_id, signed_in_at=now, role=role)
    return token, expires_at


def get_registration_state(conn: sqlite3.Connection) -> dict[str, bool]:
    return {
        "registration_code_required": bool(config.REGISTRATION_CODE),
        "registration_enabled": repository.registration_enabled(conn),
    }


def safe_user(user: dict) -> dict:
    return {
        key: user[key]
        for key in (
            "id",
            "username",
            "email",
            "role",
            "status",
            "timezone",
            "capabilities",
        )
        if key in user
    }
