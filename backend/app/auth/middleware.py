from __future__ import annotations

from fastapi import Header, HTTPException, Depends

from .service import decode_token, get_user_by_id


async def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="登录已过期或无效，请重新登录")
    user = get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if not user["is_active"]:
        raise HTTPException(status_code=401, detail="用户已被禁用")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
