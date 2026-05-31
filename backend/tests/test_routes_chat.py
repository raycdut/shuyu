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

    # Create a mock SimpleAgent
    import sqlite3
    import time
    state._sqlite = sqlite3.connect(":memory:", check_same_thread=False)
    state._sqlite.execute("PRAGMA journal_mode=WAL")
    state._sqlite.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, title TEXT DEFAULT '',
            created_at REAL NOT NULL, updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id),
            role TEXT NOT NULL, content TEXT NOT NULL DEFAULT '',
            tool_data TEXT, created_at REAL NOT NULL
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
    # Seed default prompts so lifespan can load them
    for name in ("system", "sql_gen", "plan", "plan_reflect", "report_reflect", "schema_describe"):
        state._sqlite.execute(
            "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, 1, 1, ?)",
            (name, "<instructions/>", time.time()),
        )
    state._sqlite.commit()

    from app.session.manager import SessionManager
    state.session_manager = SessionManager(sqlite_conn=state._sqlite)

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
        mock.patch("app.main.init_sqlite", return_value=None),
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

    state._sqlite.close()
    state._sqlite = None
    state.session_manager = None
    state._db_connections = []


class TestChatRoute:
    """Tests for POST /api/chat."""

    def test_agent_not_initialized(self, client):
        """Agent not initialized should return 503."""
        import app.state as state
        state.agent_loop = None

        resp = client.post("/api/chat", json={"message": "你好", "mode": "fast"})
        assert resp.status_code == 503
        assert "Agent not initialized" in resp.text

    def test_no_api_key_returns_warning(self, client):
        """Without API key, should return a warning message."""
        import app.state as state
        state.config.llm.api_key = ""

        import os
        orig = os.environ.pop("OPENAI_API_KEY", None)

        resp = client.post("/api/chat", json={
            "message": "查询数据",
            "mode": "fast",
            "session_id": "test-session-1",
            "db_id": "db-1",
        })
        data = resp.json()
        assert resp.status_code == 200
        assert "API Key" in data["reply"]
        assert data["session_id"] == "test-session-1"

        if orig is not None:
            os.environ["OPENAI_API_KEY"] = orig

    def test_no_db_id_returns_warning(self, client):
        """Without db_id, should return a warning to select a database."""
        resp = client.post("/api/chat", json={
            "message": "查询数据",
            "mode": "fast",
        })
        data = resp.json()
        assert resp.status_code == 200
        assert "选择一个数据库" in data["reply"]

    def test_successful_fast_mode(self, client):
        """Fast mode should return the agent's response."""
        import app.state as state
        state.config.llm.api_key = "sk-test"

        resp = client.post("/api/chat", json={
            "message": "查询前10个用户",
            "mode": "fast",
            "db_id": "db-1",
        })
        data = resp.json()
        assert resp.status_code == 200
        assert data["reply"] == "模拟回复：查询完成"
        assert data["session_id"] != ""

    def test_successful_quality_mode(self, client):
        """Quality mode should return the agent's response."""
        import app.state as state
        state.config.llm.api_key = "sk-test"

        resp = client.post("/api/chat", json={
            "message": "分析销售趋势",
            "mode": "quality",
            "db_id": "db-1",
        })
        data = resp.json()
        assert resp.status_code == 200
        assert data["reply"] == "模拟回复：查询完成"

    def test_session_id_preserved(self, client):
        """Session ID passed in should be returned."""
        import app.state as state
        state.config.llm.api_key = "sk-test"

        resp = client.post("/api/chat", json={
            "message": "你好",
            "mode": "fast",
            "session_id": "my-session-abc",
            "db_id": "db-1",
        })
        data = resp.json()
        assert data["session_id"] == "my-session-abc"

    def test_message_stored_in_session(self, client):
        """Messages should be stored in the session."""
        import app.state as state
        state.config.llm.api_key = "sk-test"

        resp = client.post("/api/chat", json={
            "message": "测试消息存储",
            "mode": "fast",
            "session_id": "session-msg-test",
            "db_id": "db-1",
        })
        assert resp.status_code == 200

        session = state.session_manager.get_or_create("session-msg-test")
        assert session is not None
        msgs = list(session.get_messages())
        assert len(msgs) >= 2
        assert msgs[-1]["role"] == "assistant"

    def test_invalid_db_id_handled(self, client):
        """An invalid db_id should not crash."""
        import app.state as state
        state.config.llm.api_key = "sk-test"

        resp = client.post("/api/chat", json={
            "message": "查询数据",
            "mode": "fast",
            "db_id": "nonexistent-db",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["reply"] is not None
