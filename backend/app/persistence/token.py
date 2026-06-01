"""Persistence — token usage tracking via SQLAlchemy ORM."""

from __future__ import annotations

import time

from .. import state
from ..configdb.base import scoped_session
from ..configdb.models.token import TokenUsage


def save_token_usage(prompt: int, completion: int, session_id: str | None = None) -> None:
    """Save LLM token usage to ConfigDB."""
    try:
        with scoped_session() as session:
            session.add(TokenUsage(
                model=state.config.llm.model,
                prompt=prompt,
                completion=completion,
                total=prompt + completion,
                session_id=session_id,
                created_at=time.time(),
            ))
    except Exception:
        pass
