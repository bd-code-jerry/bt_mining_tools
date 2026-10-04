from __future__ import annotations

from pydantic import BaseModel


class RegisterBody(BaseModel):
    username: str
    email: str
    password: str
    registration_code: str | None = None


class LoginBody(BaseModel):
    identifier: str | None = None
    username: str | None = None
    password: str


class SessionUser(BaseModel):
    id: int
    username: str
    email: str | None
    role: str
    status: str
    timezone: str
    capabilities: list[str]
