"""Global state — initialized at startup, shared across route modules."""

from __future__ import annotations

import sqlite3

from .agent.simple_agent import SimpleAgent
from .agent.advanced_agent import AdvancedAgent
from .agent.tools.registry import ToolRegistry
from .config import Config
from .db.base import DatabaseConnector

# --- Runtime config (loaded from SQLite at startup) ---
config: Config = None  # type: ignore[assignment]

# --- Tool registry + agent loop ---
tool_registry: ToolRegistry = None  # type: ignore[assignment]
agent_loop: SimpleAgent = None  # type: ignore[assignment]
advanced_agent: AdvancedAgent = None  # type: ignore[assignment]
connector = None  # legacy, always None in new architecture

# --- Session management ---
session_manager = None  # type: ignore[assignment]

# --- Config/session persistence (SQLite) ---
_sqlite: sqlite3.Connection | None = None

# --- Registered database connections (loaded from SQLite) ---
_db_connections: list[dict] = []

# --- Per-request active database connector (set in chat.py) ---
_active_connector: DatabaseConnector | None = None
# --- SQL queries executed during current request ---
_last_sql_queries: list[str] = []

# --- Schema prompt (filled per-database at query time) ---
schema_prompt: str = "请先在右侧配置面板中添加数据库。"

# (intentionally left blank — _system_prompt was set but never read)
