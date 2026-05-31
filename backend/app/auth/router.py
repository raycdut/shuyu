from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from .models import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserInfo,
    UserUpdateRequest,
    UserDatabaseRequest,
)
from .service import (
    create_user,
    authenticate_user,
    create_token,
    update_last_login,
    get_all_users,
    update_user,
    delete_user,
    get_user_databases,
    set_user_databases,
)
from .middleware import get_current_user, require_admin

logger = logging.getLogger("shuyu.main")

router = APIRouter()


@router.post("/api/auth/register", status_code=201)
async def register(req: RegisterRequest) -> UserInfo:
    if len(req.username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少 2 个字符")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    try:
        user = create_user(req.username, req.password, changed_by=req.username)
        return UserInfo(**user)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/api/auth/login")
async def login(req: LoginRequest) -> TokenResponse:
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    update_last_login(user["id"])
    user["last_login_at"] = datetime.now(timezone.utc).isoformat()
    token = create_token(user)
    return TokenResponse(access_token=token, user=UserInfo(**user))


@router.get("/api/auth/me")
async def me(current_user: dict = Depends(get_current_user)) -> UserInfo:
    return UserInfo(**current_user)


@router.get("/api/admin/users")
async def list_users(_admin: dict = Depends(require_admin)) -> list[UserInfo]:
    users = get_all_users()
    return [UserInfo(**u) for u in users]


@router.patch("/api/admin/users/{user_id}")
async def patch_user(user_id: str, req: UserUpdateRequest, _admin: dict = Depends(require_admin)) -> UserInfo:
    if req.role is not None and req.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="角色必须是 admin 或 user")
    user = update_user(user_id, role=req.role, is_active=req.is_active, changed_by=_admin["username"])
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserInfo(**user)


@router.delete("/api/admin/users/{user_id}")
async def remove_user(user_id: str, _admin: dict = Depends(require_admin)):
    ok = delete_user(user_id, changed_by=_admin["username"])
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"ok": True}


@router.get("/api/admin/users/{user_id}/databases")
async def list_user_databases(user_id: str, _admin: dict = Depends(require_admin)) -> dict:
    db_ids = get_user_databases(user_id)
    return {"database_ids": db_ids}


@router.put("/api/admin/users/{user_id}/databases")
async def set_user_databases_route(user_id: str, req: UserDatabaseRequest, _admin: dict = Depends(require_admin)) -> dict:
    set_user_databases(user_id, req.database_ids, changed_by=_admin["username"])
    return {"database_ids": req.database_ids}
