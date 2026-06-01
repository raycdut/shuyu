"""Config routes — get/set config, test LLM connection, prompt management."""

from __future__ import annotations

import logging
import os
import time

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .. import state
from ..configdb.base import scoped_session
from ..configdb.models.prompt import Prompt
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
    
    model_id = body.get("model_id")
    resolved_key = None
    resolved_base = None
    resolved_model = None

    if model_id:
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

PROMPT_CATEGORIES = ["system", "sql_gen", "plan", "plan_reflect", "report_reflect", "schema_describe",
                     "exec_freeform", "report_gen", "report_supplement", "report_regen"]


@router.get("/api/prompts")
async def list_prompts(category: str | None = None):
    """List all prompt versions, optionally filtered by category."""
    try:
        with scoped_session() as session:
            q = session.query(Prompt)
            if category:
                q = q.filter_by(name=category)
            rows = q.order_by(Prompt.created_at.desc()).all()
            return {
                "prompts": [
                    {"id": r.id, "name": r.name, "version": r.version,
                     "is_active": bool(r.is_active), "created_at": r.created_at}
                    for r in rows
                ]
            }
    except Exception:
        return {"prompts": []}


@router.get("/api/prompts/active")
async def get_active_prompts():
    """Get all categories' active prompt (latest active version per category).

    Falls back to hardcoded defaults for categories without DB records.
    """
    from ..configdb import _get_default_prompt_content

    result = {}
    try:
        with scoped_session() as session:
            for cat in PROMPT_CATEGORIES:
                row = session.query(Prompt).filter_by(name=cat, is_active=1).order_by(
                    Prompt.created_at.desc()
                ).first()
                if row:
                    result[cat] = {"id": row.id, "content": row.content, "version": row.version}
                else:
                    default_content = _get_default_prompt_content(cat)
                    result[cat] = {"id": None, "content": default_content, "version": None}
    except Exception:
        for cat in PROMPT_CATEGORIES:
            result[cat] = {"id": None, "content": _get_default_prompt_content(cat), "version": None}
    return result


@router.get("/api/prompts/{prompt_id}")
async def get_prompt(prompt_id: int):
    """Get a specific prompt version."""
    try:
        with scoped_session() as session:
            row = session.query(Prompt).filter_by(id=prompt_id).first()
            if not row:
                return {"error": "not found"}
            return {"id": row.id, "name": row.name, "content": row.content,
                    "version": row.version, "is_active": bool(row.is_active),
                    "created_at": row.created_at}
    except Exception:
        return {"error": "not found"}


@router.get("/api/prompts/{category}/default")
async def get_default_prompt(category: str):
    """Get the hardcoded default prompt content for a category."""
    from ..configdb import _get_default_prompt_content

    content = _get_default_prompt_content(category)
    if content is None:
        return {"error": f"unknown category: {category}"}
    return {"category": category, "content": content}


@router.put("/api/prompts")
async def upsert_prompt(req: Request):
    """Create or update a prompt category (creates a new version).

    Request body:
      - category (str): prompt category name
      - content (str): prompt content
      - name (str, optional): legacy alias for category
    """
    body = await req.json()
    content = body.get("content", "")
    category = body.get("category") or body.get("name", "system")

    try:
        with scoped_session() as session:
            row = session.query(Prompt.version).filter_by(name=category).order_by(
                Prompt.version.desc()
            ).first()
            new_version = (row[0] if row else 0) + 1

            session.query(Prompt).filter_by(name=category).update(
                {"is_active": 0}, synchronize_session=False
            )
            session.add(Prompt(
                name=category,
                content=content,
                version=new_version,
                is_active=1,
                created_at=time.time(),
            ))
        return {"ok": True, "version": new_version}
    except Exception:
        return {"ok": False, "error": "failed to save prompt"}


@router.patch("/api/prompts/{prompt_id}/activate")
async def activate_prompt_version(prompt_id: int):
    """Activate a specific prompt version, deactivating others in the same category."""
    try:
        with scoped_session() as session:
            row = session.query(Prompt).filter_by(id=prompt_id).first()
            if not row:
                return {"ok": False, "error": "not found"}
            category = row.name
            session.query(Prompt).filter_by(name=category).update(
                {"is_active": 0}, synchronize_session=False
            )
            session.query(Prompt).filter_by(id=prompt_id).update(
                {"is_active": 1}, synchronize_session=False
            )
        return {"ok": True}
    except Exception:
        return {"ok": False, "error": "failed to activate prompt"}
