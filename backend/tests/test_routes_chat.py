"""Tests for routes/chat.py — /api/chat endpoint."""

from __future__ import annotations

import json
import pytest
from unittest import mock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Set up a minimal app state with mock agents."""
    import app.state as state
    from app.config import Config, LLMConfig
    from app.auth.service import init_auth_config

    init_auth_config()
    state.config = Config()
    state.config.llm = LLMConfig(api_key="sk-test", api_base="https://test.api.com", model="gpt-4o", provider="openai")

    from app.session.manager import SessionManager
    state.session_manager = SessionManager()

    from app.main import app as _app
    from app.agent.simple_agent import SimpleAgent as _SimpleAgent
    from app.agent.advanced_agent import AdvancedAgent as _AdvancedAgent
    from app.agent.tools.registry import ToolRegistry

    state.tool_registry = ToolRegistry()

    async def mock_agent_run(messages, **kw):
        return {"content": "模拟回复：查询完成", "tool_calls": [], "sql_queries": []}

    mock_loop = mock.MagicMock(spec=_SimpleAgent)
    mock_loop.run = mock_agent_run
    mock_advanced = mock.MagicMock(spec=_AdvancedAgent)
    mock_advanced.run = mock_agent_run

    state._db_connections = [
        {
            "id": "db-1",
            "name": "TestDB",
            "type": "duckdb",
            "path": ":memory:",
            "include_tables": None,
            "exclude_tables": None,
            "is_active": True,
            "schema_status": "imported",
        }
    ]

    patchers = [
        mock.patch("app.main.init_configdb", return_value=None),
        mock.patch("app.main.load_config_sqlite", return_value=None),
        mock.patch("app.main.load_db_connections_sqlite", return_value=None),
        mock.patch("app.main.load_config", return_value=state.config),
        mock.patch("app.main.SimpleAgent", return_value=mock_loop),
        mock.patch("app.main.AdvancedAgent", return_value=mock_advanced),
    ]
    for p in patchers:
        p.start()

    with TestClient(_app) as c:
        yield c

    for p in patchers:
        p.stop()

    state.session_manager = None
    state._db_connections = []