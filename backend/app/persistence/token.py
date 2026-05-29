"""Persistence — token usage tracking."""

from __future__ import annotations

import time

from .. import state


def save_token_usage(prompt: int, completion: int, session_id: str | None = None) -> None:
    """Save LLM token usage to SQLite."""
    sql = state._sqlite
    if sql is None:
        return
    try:
        sql.execute(
            "INSERT INTO token_usage (model, prompt, completion, total, session_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (state.config.llm.model, prompt, completion, prompt + completion, session_id, time.time()),
        )
        sql.commit()
    except Exception:
        pass
