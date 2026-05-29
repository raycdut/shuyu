"""LLM call helpers — unified call_llm function + schema prompt builder."""

from __future__ import annotations

import logging
import os

from . import state
from .agent.tools.sql_tool import handle_sql_query
from .config_store import _save_token_usage

logger = logging.getLogger("shuyu.main")


def build_schema_prompt(tables) -> str:
    """Build the schema description injected into agent system prompt."""
    lines = ["以下是数据库中的表和字段：\n"]
    for t in tables:
        lines.append(t.to_prompt_block())
    return "\n".join(lines)


async def handle_query_database(question: str) -> str:
    """Tool handler: query the database via natural language question.

    Uses state._active_connector (set per-request in chat route).
    """
    logger.info(f"SQL tool: processing question '{question[:80]}'")

    if state._active_connector is None:
        return "⚠️ 没有选中的数据库，无法查询。请先在左侧选择一个数据库。"

    tables = state._active_connector.get_schema()
    schema_text = build_schema_prompt(tables)

    async def _call_llm_for_sql(msgs):
        resp = await call_llm(msgs)
        return resp.choices[0].message.content

    return await handle_sql_query(
        question=question,
        connector=state._active_connector,
        schema_prompt=schema_text,
        call_llm_func=_call_llm_for_sql,
        max_rows=state.config.safety.max_rows,
    )


async def call_llm(messages: list[dict], **kwargs) -> object:
    """Unified LLM call — routes to the configured provider, with retry."""
    from openai import AsyncOpenAI
    import asyncio

    client_kwargs = {}
    if state.config.llm.api_base:
        client_kwargs["base_url"] = state.config.llm.api_base

    api_key = state.config.llm.api_key or os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        client_kwargs["api_key"] = api_key

    # DeepSeek V4 models need thinking mode enabled for tool calling
    if state.config.llm.model.startswith("deepseek-v4"):
        kwargs["extra_body"] = {"thinking": {"type": "enabled"}}

    client = AsyncOpenAI(**client_kwargs)

    last_error = None
    for attempt in range(3):
        try:
            response = await client.chat.completions.create(
                model=state.config.llm.model,
                messages=messages,
                timeout=state.config.llm.timeout,
                **kwargs,
            )
            # Log token usage if available
            if hasattr(response, "usage") and response.usage:
                u = response.usage
                logger.info(f"Token: prompt={u.prompt_tokens}, completion={u.completion_tokens}, total={u.prompt_tokens + u.completion_tokens}")
                _save_token_usage(u.prompt_tokens, u.completion_tokens)
            return response
        except Exception as e:
            last_error = e
            err_str = str(e)
            # Don't retry auth errors or bad requests
            if "401" in err_str or "403" in err_str or "invalid" in err_str.lower():
                logger.error(f"LLM call failed (non-retryable): {e}")
                raise
            if attempt < 2:
                wait = 2 ** attempt
                logger.warning(f"LLM call attempt {attempt + 1} failed, retrying in {wait}s: {e}")
                await asyncio.sleep(wait)

    logger.error(f"LLM call failed after 3 attempts: {last_error}")
    raise last_error
