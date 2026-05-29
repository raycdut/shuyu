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
