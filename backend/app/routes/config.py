"""Config routes — get/set config, test LLM connection"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Request

from .. import state
from ..config_store import save_config_sqlite
from ..llm import call_llm
from ..models.schemas import ConfigUpdate, LLMTestResult

logger = logging.getLogger("shuyu.main")

router = APIRouter()


@router.get("/api/config")
async def get_config():
    """Get current runtime configuration."""
    return {
        "llm": {
            "provider": state.config.llm.provider,
            "model": state.config.llm.model,
            "api_key": "••••••" if state.config.llm.api_key else "",
            "api_base": state.config.llm.api_base or "",
            "timeout": state.config.llm.timeout,
        },
        "safety": {
            "read_only": state.config.safety.read_only,
            "require_approval": True,
            "max_rows": state.config.safety.max_rows,
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
async def test_llm(req: Request):
    """Test the LLM connection with provided (or saved) config."""
    body = await req.json() if req.headers.get("content-type") == "application/json" else {}
    logger.info(f"POST /api/config/llm/test: provider={body.get('provider','?')} model={body.get('model','?')}")

    test_key = body.get("api_key") or state.config.llm.api_key or os.environ.get("OPENAI_API_KEY", "")
    test_base = body.get("api_base") or state.config.llm.api_base or ""
    test_model = body.get("model") or state.config.llm.model or "gpt-4o"

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
