"""Persistence — config load/save via SQLAlchemy ORM."""

from __future__ import annotations

import logging
import time

from .. import state
from ..configdb.base import scoped_session
from ..configdb.models.config import LlmProvider, Setting

logger = logging.getLogger("shuyu.main")


def load_config_sqlite() -> None:
    """Load config from ConfigDB into runtime config object."""
    try:
        with scoped_session() as session:
            row = session.query(LlmProvider).filter_by(is_active=1).first()
            if row:
                state.config.llm.provider = row.provider or "openai"
                state.config.llm.model = row.model or "gpt-4o"
                state.config.llm.api_key = row.api_key or ""
                state.config.llm.api_base = row.api_base or ""
                state.config.llm.timeout = row.timeout or 120

            settings_rows = session.query(Setting).all()
            for s in settings_rows:
                if s.key == "safety_read_only":
                    state.config.safety.read_only = s.value == "true"
                elif s.key == "safety_max_rows":
                    state.config.safety.max_rows = int(s.value)
    except Exception:
        pass


def save_config_sqlite() -> None:
    """Save runtime config to ConfigDB."""
    try:
        with scoped_session() as session:
            existing = session.query(LlmProvider).filter_by(is_active=1).first()
            if existing:
                existing.provider = state.config.llm.provider
                existing.model = state.config.llm.model
                existing.api_key = state.config.llm.api_key
                existing.api_base = state.config.llm.api_base or ""
                existing.timeout = state.config.llm.timeout
            else:
                session.add(LlmProvider(
                    name=state.config.llm.provider,
                    provider=state.config.llm.provider,
                    model=state.config.llm.model,
                    api_key=state.config.llm.api_key,
                    api_base=state.config.llm.api_base or "",
                    timeout=state.config.llm.timeout,
                    is_active=1,
                    created_at=time.time(),
                ))

            for key, value in [
                ("safety_read_only", str(state.config.safety.read_only).lower()),
                ("safety_max_rows", str(state.config.safety.max_rows)),
            ]:
                s = session.query(Setting).filter_by(key=key).first()
                if s:
                    s.value = value
                else:
                    session.add(Setting(key=key, value=value))
    except Exception:
        pass
