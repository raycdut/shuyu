"""Global state — initialized at startup, shared across route modules."""

from __future__ import annotations

import contextvars
import sqlite3
from typing import TYPE_CHECKING

from .agent.tools.registry import ToolRegistry
from .config import Config
from .db.base import DatabaseConnector

if TYPE_CHECKING:
    from .agent.simple_agent import SimpleAgent
    from .agent.advanced_agent import AdvancedAgent

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

# --- Per-request runtime context (do NOT store request-specific objects as globals) ---
request_active_connector: contextvars.ContextVar[DatabaseConnector | None] = contextvars.ContextVar(
    "request_active_connector",
    default=None,
)
request_schema_prompt: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_schema_prompt",
    default=None,
)
request_sql_queries: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar(
    "request_sql_queries",
    default=None,
)
request_query_results: contextvars.ContextVar[list[dict] | None] = contextvars.ContextVar(
    "request_query_results",
    default=None,
)
request_active_db_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_active_db_id",
    default=None,
)


def get_request_connector() -> DatabaseConnector | None:
    """Get the active connector bound to the current request context."""
    return request_active_connector.get()


def get_request_schema_prompt() -> str | None:
    """Get the schema prompt bound to the current request context."""
    return request_schema_prompt.get()


def get_request_sql_queries() -> list[str]:
    """Get collected SQL queries for the current request context."""
    return request_sql_queries.get() or []


def get_request_query_results() -> list[dict]:
    """Get collected structured query results for the current request context."""
    return request_query_results.get() or []


def get_request_active_db_id() -> str | None:
    """Get the active database ID for the current request context."""
    return request_active_db_id.get()

# --- Schema prompt (filled per-database at query time) ---
schema_prompt: str = "请先在右侧配置面板中添加数据库。"

# (intentionally left blank — _system_prompt was set but never read)
