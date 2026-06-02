from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..auth.middleware import get_current_user, require_admin
from .service import (
    get_system_config,
    get_system_config_masked,
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
    return get_system_config_masked()


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


@router.get("/api/admin/rag/stats")
async def admin_rag_stats(_admin: dict = Depends(require_admin)) -> dict:
    from ..metrics.rag_metrics import get_rag_metrics
    return get_rag_metrics()


@router.post("/api/admin/rag/test")
async def admin_rag_test(body: dict[str, Any], _admin: dict = Depends(require_admin)) -> dict:
    """Test RAG embedding connection with the provided or current config."""
    from ..embedding.service import create_embedding_service
    from ..metrics.rag_metrics import get_rag_metrics
    cfg = {**get_system_config().get("rag", {}), **body.get("rag", {})}
    api_key = cfg.get("api_key", "") or None
    if not api_key:
        raise HTTPException(400, "API Key is required")
    try:
        svc = create_embedding_service(
            provider=cfg.get("provider", "openai"),
            api_key=api_key,
            model=cfg.get("model", "text-embedding-3-small"),
            api_base=cfg.get("api_base") or None,
        )
        result = await svc.embed("test connection")
        return {"ok": True, "dimension": len(result), "message": "连接成功"}
    except Exception as e:
        return {"ok": False, "message": f"连接失败: {e}"}
