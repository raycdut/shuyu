"""LLM client — unified call_llm with retry, timeout, token tracking."""

from __future__ import annotations

import asyncio
import logging
import os

from . import state
from .persistence.token import save_token_usage

logger = logging.getLogger("shuyu.main")


async def call_llm(messages: list[dict], **kwargs) -> object:
    """Unified LLM call — routes to the configured provider, with retry."""
    from openai import AsyncOpenAI

    client_kwargs = {}
    if state.config.llm.api_base:
        client_kwargs["base_url"] = state.config.llm.api_base

    api_key = state.config.llm.api_key or os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        client_kwargs["api_key"] = api_key

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
            if hasattr(response, "usage") and response.usage:
                u = response.usage
                logger.info(f"Token: prompt={u.prompt_tokens}, completion={u.completion_tokens}, total={u.prompt_tokens + u.completion_tokens}")
                save_token_usage(u.prompt_tokens, u.completion_tokens)
            return response
        except Exception as e:
            last_error = e
            err_str = str(e)
            if "401" in err_str or "403" in err_str or "invalid" in err_str.lower():
                logger.error(f"LLM call failed (non-retryable): {e}")
                raise
            if attempt < 2:
                wait = 2 ** attempt
                logger.warning(f"LLM call attempt {attempt + 1} failed, retrying in {wait}s: {e}")
                await asyncio.sleep(wait)

    logger.error(f"LLM call failed after 3 attempts: {last_error}")
    raise last_error
