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
