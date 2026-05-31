"""Persistence — SQLite init: DDL + seed data."""

from __future__ import annotations

import logging
from pathlib import Path

from .. import state

logger = logging.getLogger("shuyu.main")

DEFAULT_PROMPT = """<instructions>
  <role>data-analyst</role>
  <language>zh-CN</language>
  <workflow>
    <step>1. 理解用户的问题</step>
    <step>2. 必须调用 query_database 工具查询数据，不能凭表名猜测</step>
    <step>3. 根据查询结果回答用户</step>
    <step>4. 如果用户的问题不明确，主动澄清</step>
  </workflow>
  <rules>
    <rule>如果用户问「帮我分析一下」，主动问他们想分析什么维度和时间段</rule>
    <rule>使用中文回答</rule>
    <rule>回答简洁，突出关键数据</rule>
    <rule>如果工具返回了数据，直接根据数据回答，不要编造</rule>
  </rules>
</instructions>"""


def init_sqlite() -> None:
    """Initialize SQLite database with schema and seed data."""
    import sqlite3
    import time

    logger.info(f"Initializing SQLite: {state.config.storage.path}")
    db_path = Path(state.config.storage.path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    state._sqlite = sqlite3.connect(str(db_path))
    state._sqlite.execute("PRAGMA journal_mode=WAL")
    state._sqlite.execute("PRAGMA busy_timeout=5000")

    state._sqlite.executescript("""
        CREATE TABLE IF NOT EXISTS llm_providers (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            provider   TEXT NOT NULL DEFAULT 'openai',
            model      TEXT NOT NULL DEFAULT 'gpt-4o',
            api_key    TEXT DEFAULT '',
            api_base   TEXT DEFAULT '',
            timeout    INTEGER DEFAULT 120,
            is_active  INTEGER DEFAULT 0,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        INSERT OR IGNORE INTO settings (key, value) VALUES ('safety_read_only', 'true');
        INSERT OR IGNORE INTO settings (key, value) VALUES ('safety_max_rows', '1000');
        CREATE TABLE IF NOT EXISTS databases (
            id                TEXT PRIMARY KEY,
            name              TEXT NOT NULL,
            type              TEXT NOT NULL DEFAULT 'duckdb',
            path              TEXT,
            connection_string TEXT,
            host              TEXT,
            port              INTEGER,
            username          TEXT,
            password          TEXT,
            db_name           TEXT,
            include_tables    TEXT,
            exclude_tables    TEXT,
            is_active         INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id         TEXT PRIMARY KEY,
            title      TEXT DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id),
            role      TEXT NOT NULL,
            content   TEXT NOT NULL DEFAULT '',
            tool_data TEXT,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS token_usage (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            model      TEXT NOT NULL,
            prompt     INTEGER NOT NULL DEFAULT 0,
            completion INTEGER NOT NULL DEFAULT 0,
            total      INTEGER NOT NULL DEFAULT 0,
            session_id TEXT,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS prompts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL DEFAULT 'default',
            content    TEXT NOT NULL,
            version    INTEGER NOT NULL DEFAULT 1,
            is_active  INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL
        );
    """)

    # Seed default prompt if empty
    count = state._sqlite.execute("SELECT COUNT(*) FROM prompts").fetchone()[0]
    if count == 0:
        state._sqlite.execute(
            "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, 1, 1, ?)",
            ("default", DEFAULT_PROMPT, time.time()),
        )
        state._sqlite.commit()

    # Migrate existing tables: add timeout column if missing
    try:
        state._sqlite.execute("ALTER TABLE llm_providers ADD COLUMN timeout INTEGER DEFAULT 120")
    except Exception:
        pass

    # ---- Auth tables ----
    _migrate_auth_tables()

    # ---- Config tables ----
    _migrate_config_tables()


def _migrate_auth_tables():
    """Create users + user_databases tables, add user_id to sessions."""
    state._sqlite.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            TEXT PRIMARY KEY,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'user'
                          CHECK(role IN ('admin', 'user')),
            is_active     INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS user_databases (
            user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            database_id TEXT NOT NULL REFERENCES databases(id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, database_id)
        );
    """)
    try:
        state._sqlite.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT REFERENCES users(id)")
    except Exception:
        pass
    state._sqlite.commit()


def _migrate_config_tables():
    """Create system_config + user_configs + config_changelog tables."""
    state._sqlite.executescript("""
        CREATE TABLE IF NOT EXISTS system_config (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            config      TEXT NOT NULL DEFAULT '{}',
            updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_by  TEXT
        );
        CREATE TABLE IF NOT EXISTS user_configs (
            user_id     TEXT PRIMARY KEY,
            config      TEXT NOT NULL DEFAULT '{}',
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS config_changelog (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            config_type TEXT NOT NULL CHECK (config_type IN ('system', 'user')),
            user_id     TEXT,
            changed_by  TEXT NOT NULL,
            summary     TEXT NOT NULL,
            diff        TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    state._sqlite.commit()
    _migrate_llm_providers_to_models()


def _migrate_llm_providers_to_models():
    """Migrate old llm_providers table data into system_config.models.

    Scenarios handled:
    1. system_config (id=1) does NOT exist → seed from llm_providers
    2. system_config exists but has no models field (only provider_pool) → merge llm_providers into models
    3. system_config already has models → skip (already migrated or configured via UI)
    """
    import json
    import uuid

    sql = state._sqlite
    if sql is None:
        return

    # Look for an active provider in the old table
    row = sql.execute(
        "SELECT provider, model, api_key, api_base, timeout, name FROM llm_providers WHERE is_active = 1 LIMIT 1"
    ).fetchone()
    if not row:
        return

    provider, model, api_key, api_base, timeout, name = row
    if not api_key:
        return

    logger.info(f"Found active llm_providers entry: {provider}/{model}, migrating to models format...")

    # Build a provider-friendly name if none exists
    if not name or name == provider:
        name = f"{provider.capitalize()} - {model}"

    # Build base URL map for common providers
    base_urls = {
        "openai": "https://api.openai.com/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "ollama": "http://localhost:11434/v1",
    }
    if not api_base and provider in base_urls:
        api_base = base_urls[provider]

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    models_entry = {
        "id": f"migrated-{provider}-{uuid.uuid4().hex[:6]}",
        "name": name,
        "provider": provider,
        "model": model or "gpt-4o",
        "api_key": api_key or "",
        "api_base": api_base or "",
        "timeout": timeout or 120,
        "enabled": True,
        "is_system_default": True,
    }

    # Check if system_config already exists
    existing = sql.execute("SELECT config FROM system_config WHERE id = 1").fetchone()
    if existing:
        try:
            existing_config = json.loads(existing[0])
        except (json.JSONDecodeError, TypeError):
            existing_config = {}

        # If it already has models, skip (already migrated or user configured)
        existing_models = existing_config.get("llm", {}).get("models", [])
        if existing_models:
            logger.info("system_config already has models, skipping migration")
            return

        # Merge the migrated model into existing config (preserving provider_pool etc.)
        existing_config.setdefault("llm", {})
        existing_config["llm"]["models"] = [models_entry]
        sql.execute(
            "UPDATE system_config SET config = ?, updated_at = ?, updated_by = ? WHERE id = 1",
            (json.dumps(existing_config), now, "system-migration"),
        )
        sql.commit()
        logger.info(f"Migration complete: merged {provider}/{model} into existing system_config")
    else:
        # system_config doesn't exist — seed it fresh
        config = {"llm": {"models": [models_entry]}}
        sql.execute(
            "INSERT INTO system_config (id, config, updated_at, updated_by) VALUES (1, ?, ?, ?)",
            (json.dumps(config), now, "system-migration"),
        )
        sql.commit()
        logger.info(f"Migration complete: system_config seeded with {provider}/{model}")
