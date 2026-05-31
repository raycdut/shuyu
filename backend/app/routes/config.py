"""Config routes — get/set config, test LLM connection"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .. import state
from ..persistence.config import save_config_sqlite
from ..client import call_llm
from ..models.config import ConfigUpdate, LLMTestResult
from ..auth.middleware import get_current_user
from ..admin_config.service import get_merged_config, get_system_config

logger = logging.getLogger("shuyu.main")

router = APIRouter()

security = HTTPBearer(auto_error=False)


async def optional_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    """Get current user if token is provided, otherwise return None."""
    if credentials is None:
        return None
    try:
        from ..auth.middleware import get_current_user as _get_user
        return await _get_user(authorization=f"Bearer {credentials.credentials}")
    except Exception:
        return None


@router.get("/api/config")
async def get_config(current_user: dict | None = Depends(optional_current_user)):
    """Get current runtime configuration (merged with user config if authenticated)."""
    user_id = current_user["id"] if current_user else None
    merged = get_merged_config(user_id)
    return {
        "llm": {
            "id": merged["llm"].get("id"),
            "name": merged["llm"].get("name", merged["llm"]["model"]),
            "provider": merged["llm"]["provider"],
            "model": merged["llm"]["model"],
            "api_key": "••••••" if merged["llm"]["api_key"] else "",
            "api_base": merged["llm"]["api_base"] or "",
            "timeout": merged["llm"]["timeout"],
        },
        "safety": {
            "read_only": merged["safety"]["read_only"],
            "require_approval": merged["safety"]["require_approval"],
            "max_rows": merged["safety"]["max_rows"],
        },
    }


@router.post("/api/config")
async def update_config(req: ConfigUpdate):
    """Update runtime configuration."""
    if req.llm:
        if "provider" in req.llm:
            state.config.llm.provider = req.llm["provider"]
        if "model" in req.llm:
            state.config.llm.model = req.llm["model"]
        if "api_key" in req.llm and req.llm["api_key"] and req.llm["api_key"] != "••••••":
            state.config.llm.api_key = req.llm["api_key"]
        if "api_base" in req.llm:
            state.config.llm.api_base = req.llm["api_base"] or None
        if "timeout" in req.llm:
            state.config.llm.timeout = int(req.llm["timeout"])
        save_config_sqlite()
    if req.safety:
        if "read_only" in req.safety:
            state.config.safety.read_only = req.safety["read_only"]
        if "max_rows" in req.safety:
            state.config.safety.max_rows = req.safety["max_rows"]
        save_config_sqlite()
    return {"ok": True}


@router.post("/api/config/llm/test", response_model=LLMTestResult)
async def test_llm(req: Request, current_user: dict | None = Depends(optional_current_user)):
    """Test the LLM connection with provided (or saved) config."""
    body = await req.json() if req.headers.get("content-type") == "application/json" else {}
    
    user_id = current_user["id"] if current_user else None
    merged = get_merged_config(user_id)
    
    # Priority: 1. model_id lookup → 2. Request body → 3. User/System Config → 4. Env
    model_id = body.get("model_id")
    resolved_key = None
    resolved_base = None
    resolved_model = None

    if model_id:
        # Look up the model by ID from the unmasked system config
        system = get_system_config()
        for m in system.get("llm", {}).get("models", []):
            if m.get("id") == model_id:
                resolved_key = m.get("api_key", "")
                resolved_base = m.get("api_base", "") or ""
                resolved_model = m.get("model", "")
                break

    test_key = (
        resolved_key
        or body.get("api_key")
        or merged["llm"].get("api_key")
        or os.environ.get("OPENAI_API_KEY", "")
    )
    test_base = resolved_base or body.get("api_base") or merged["llm"].get("api_base") or ""
    test_model = resolved_model or body.get("model") or merged["llm"].get("model") or "gpt-4o"
    test_provider = body.get("provider") or merged["llm"].get("provider") or "openai"

    logger.info(f"POST /api/config/llm/test: provider={test_provider} model={test_model} base={test_base} model_id={model_id}")

    if not test_key:
        return LLMTestResult(ok=False, message="未设置 API Key")

    try:
        from openai import AsyncOpenAI

        client_kwargs = {"api_key": test_key}
        if test_base:
            client_kwargs["base_url"] = test_base

        client = AsyncOpenAI(**client_kwargs)
        await client.chat.completions.create(
            model=test_model,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=5,
        )
        return LLMTestResult(ok=True, message="连接成功")
    except Exception as e:
        err = str(e)
        return LLMTestResult(ok=False, message=err[:200])


# ===== Prompt management =====


@router.get("/api/prompts")
async def list_prompts():
    """List all prompt versions."""
    if state._sqlite is None:
        return {"prompts": []}
    rows = state._sqlite.execute(
        "SELECT id, name, version, is_active, created_at FROM prompts ORDER BY created_at DESC"
    ).fetchall()
    return {
        "prompts": [
            {"id": r[0], "name": r[1], "version": r[2], "is_active": bool(r[3]), "created_at": r[4]}
            for r in rows
        ]
    }


@router.get("/api/prompts/{prompt_id}")
async def get_prompt(prompt_id: int):
    """Get a specific prompt version."""
    if state._sqlite is None:
        return {"error": "no db"}
    row = state._sqlite.execute(
        "SELECT id, name, content, version, is_active, created_at FROM prompts WHERE id = ?",
        (prompt_id,),
    ).fetchone()
    if not row:
        return {"error": "not found"}
    return {"id": row[0], "name": row[1], "content": row[2], "version": row[3], "is_active": bool(row[4]), "created_at": row[5]}


@router.put("/api/prompts")
async def upsert_prompt(req: Request):
    """Create or update the active prompt (creates a new version)."""
    body = await req.json()
    content = body.get("content", "")
    name = body.get("name", "default")
    import time

    if state._sqlite is None:
        return {"ok": False, "error": "no db"}

    # Get current max version
    row = state._sqlite.execute(
        "SELECT MAX(version) FROM prompts WHERE name = ?", (name,)
    ).fetchone()
    new_version = (row[0] or 0) + 1

    # Deactivate old versions
    state._sqlite.execute("UPDATE prompts SET is_active = 0 WHERE name = ?", (name,))
    # Insert new version as active
    state._sqlite.execute(
        "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
        (name, content, new_version, time.time()),
    )
    state._sqlite.commit()
    return {"ok": True, "version": new_version}
