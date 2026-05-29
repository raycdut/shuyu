"""Persistence — config load/save."""

from __future__ import annotations

import logging
import time

from .. import state

logger = logging.getLogger("shuyu.main")


def load_config_sqlite() -> None:
    """Load config from SQLite into runtime config object."""
    sql = state._sqlite
    if sql is None:
        return
    try:
        _migrate_old_config()

        row = sql.execute(
            "SELECT provider, model, api_key, api_base, timeout FROM llm_providers WHERE is_active = 1"
        ).fetchone()
        if row:
            state.config.llm.provider = row[0] or "openai"
            state.config.llm.model = row[1] or "gpt-4o"
            state.config.llm.api_key = row[2] or ""
            state.config.llm.api_base = row[3] or ""
            state.config.llm.timeout = row[4] or 120

        rows = sql.execute("SELECT key, value FROM settings").fetchall()
        for key, value in rows:
            if key == "safety_read_only":
                state.config.safety.read_only = value == "true"
            elif key == "safety_max_rows":
                state.config.safety.max_rows = int(value)
    except Exception:
        pass


def save_config_sqlite() -> None:
    """Save runtime config to SQLite."""
    sql = state._sqlite
    if sql is None:
        return
    try:
        logger.info(f"Saving config: LLM={state.config.llm.provider}/{state.config.llm.model}")
        existing = sql.execute("SELECT id FROM llm_providers WHERE is_active = 1").fetchone()
        if existing:
            sql.execute(
                "UPDATE llm_providers SET provider=?, model=?, api_key=?, api_base=?, timeout=? WHERE id=?",
                (state.config.llm.provider, state.config.llm.model,
                 state.config.llm.api_key, state.config.llm.api_base or "", state.config.llm.timeout, existing[0]),
            )
        else:
            sql.execute(
                "INSERT INTO llm_providers (name, provider, model, api_key, api_base, timeout, is_active, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                (state.config.llm.provider, state.config.llm.provider, state.config.llm.model,
                 state.config.llm.api_key, state.config.llm.api_base or "", state.config.llm.timeout, time.time()),
            )

        sql.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    ("safety_read_only", str(state.config.safety.read_only).lower()))
        sql.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    ("safety_max_rows", str(state.config.safety.max_rows)))
        sql.commit()
    except Exception:
        pass


def _migrate_old_config() -> None:
    """Migrate from old key-value config table to new schema."""
    sql = state._sqlite
    if sql is None:
        return
    try:
        old = sql.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='config'"
        ).fetchone()
        if not old:
            return
        logger.info("Old config table found, migrating to new schema...")

        rows = sql.execute("SELECT key, value FROM config").fetchall()
        if not rows:
            return

        pairs = dict(rows)
        has_llm = "llm_provider" in pairs or "llm_model" in pairs

        if has_llm:
            existing_active = sql.execute("SELECT id FROM llm_providers WHERE is_active = 1").fetchone()
            if existing_active:
                sql.execute("DROP TABLE IF EXISTS config")
                sql.commit()
                return

            sql.execute(
                "INSERT INTO llm_providers (name, provider, model, api_key, api_base, timeout, is_active, created_at) "
                "VALUES (?, ?, ?, ?, ?, 60, 1, ?)",
                (pairs.get("llm_provider", "default"), pairs.get("llm_provider", "openai"),
                 pairs.get("llm_model", "gpt-4o"), pairs.get("llm_api_key", ""),
                 pairs.get("llm_api_base", ""), time.time()),
            )

            for old_key, new_key in [("safety_read_only", "safety_read_only"),
                                      ("safety_max_rows", "safety_max_rows")]:
                if old_key in pairs:
                    sql.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (new_key, pairs[old_key]))

        sql.execute("DROP TABLE IF EXISTS config")
        sql.commit()
    except Exception:
        pass
