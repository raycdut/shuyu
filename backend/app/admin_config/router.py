from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..auth.middleware import get_current_user, require_admin
from .service import (
    get_system_config,
    update_system_config,
    get_user_config,
    update_user_config,
    get_merged_config,
    get_user_available_options,
    get_config_changelog,
)

logger = logging.getLogger("shuyu.main")

router = APIRouter()


@router.get("/api/admin/config")
async def admin_get_config(_admin: dict = Depends(require_admin)) -> dict:
    return get_system_config()


@router.put("/api/admin/config")
async def admin_put_config(body: dict[str, Any], _admin: dict = Depends(require_admin)) -> dict:
    return update_system_config(body, updated_by=_admin["username"])


@router.patch("/api/admin/config")
async def admin_patch_config(body: dict[str, Any], _admin: dict = Depends(require_admin)) -> dict:
    return update_system_config(body, updated_by=_admin["username"])


@router.get("/api/admin/config/changelog")
async def admin_config_changelog(admin: dict = Depends(require_admin)) -> list[dict]:
    return get_config_changelog("system")


@router.get("/api/user/config")
async def user_get_config(current_user: dict = Depends(get_current_user)) -> dict:
    return get_merged_config(current_user["id"])


@router.put("/api/user/config")
async def user_put_config(body: dict[str, Any], current_user: dict = Depends(get_current_user)) -> dict:
    return update_user_config(current_user["id"], body)


@router.get("/api/user/config/available")
async def user_available_options(current_user: dict = Depends(get_current_user)) -> dict:
    return get_user_available_options(current_user["id"])


@router.get("/api/user/config/history")
async def user_config_history(current_user: dict = Depends(get_current_user)) -> list[dict]:
    return get_config_changelog("user", current_user["id"])
