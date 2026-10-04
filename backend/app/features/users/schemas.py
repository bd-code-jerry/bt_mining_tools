from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel


Role = Literal["admin", "member", "user"]
AccountStatus = Literal["active", "disabled"]


class CreateUserBody(BaseModel):
    username: str
    email: str
    password: str
    role: Role = "member"


class ApproveUserBody(BaseModel):
    role: Role = "member"


class RoleBody(BaseModel):
    role: Role


class StatusBody(BaseModel):
    status: AccountStatus


class PasswordResetBody(BaseModel):
    new_password: str


class RegistrationBody(BaseModel):
    enabled: bool


class EmailBody(BaseModel):
    email: str | None


class LoginEventFilters(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    account_id: int | None = None
    role: Role | None = None
