from __future__ import annotations

from pydantic import BaseModel


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserInfo"


class UserInfo(BaseModel):
    id: str
    username: str
    role: str
    is_active: bool = True
    created_at: str | None = None
    last_login_at: str | None = None


class UserUpdateRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class UserDatabaseRequest(BaseModel):
    database_ids: list[str]
