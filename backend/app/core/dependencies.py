from __future__ import annotations

from fastapi import HTTPException, Request, status

from .config import SESSION_COOKIE_NAME
from .database import db_connection
from .permissions import capabilities_for_role
from .security import hash_session_token, unix_now, utc_now_iso


def get_current_user(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in.")

    token_hash = hash_session_token(token)
    now = unix_now()
    denial_message: str | None = None
    user: dict | None = None
    with db_connection() as conn:
        row = conn.execute(
            """SELECT users.id, users.username, users.email, users.role, users.status,
                      users.created_at, users.last_login_at, users.timezone,
                      sessions.id AS session_id, sessions.expires_at
               FROM sessions JOIN users ON users.id = sessions.user_id
               WHERE sessions.token_hash = ?""",
            (token_hash,),
        ).fetchone()
        if row is None:
            conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            denial_message = "Your session has expired. Please sign in again."
        elif int(row["expires_at"]) <= now:
            conn.execute("DELETE FROM sessions WHERE id = ?", (row["session_id"],))
            denial_message = "Your session has expired. Please sign in again."
        elif row["status"] != "active":
            conn.execute("DELETE FROM sessions WHERE id = ?", (row["session_id"],))
            denial_message = "This account is not active. Please contact an administrator."
        else:
            conn.execute(
                "UPDATE sessions SET last_activity_at = ? WHERE id = ?",
                (utc_now_iso(), row["session_id"]),
            )
            user = {
                key: row[key]
                for key in (
                    "id",
                    "username",
                    "email",
                    "role",
                    "status",
                    "created_at",
                    "last_login_at",
                    "timezone",
                )
            }
            user["capabilities"] = capabilities_for_role(user["role"])

    if denial_message:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=denial_message)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in.")
    return user
