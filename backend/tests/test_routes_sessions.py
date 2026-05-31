"""Tests for session routes — list, get messages, rename, delete."""

from __future__ import annotations

import time
import pytest
from fastapi.testclient import TestClient
from app.main import app


def _add_session(session_id: str, title: str = "", messages: list[dict] | None = None):
    """Helper to add a test session directly into the session manager."""
    import app.state as state
    from app.session.manager import Session

    sess = Session(session_id, title=title)
    if messages:
        sess.messages = list(messages)
        sess.last_active = time.time()
    state.session_manager._sessions[session_id] = sess
    return sess


@pytest.fixture(autouse=True)
def setup():
    """Set up Config and a fresh SessionManager before each test, and clean up after."""
    import app.state as state
    from app.config import Config
    from app.session.manager import SessionManager

    state.config = Config()
    state.config.llm.api_key = "test-key"
    state.session_manager = SessionManager()
    yield
    state.session_manager = None


@pytest.fixture
def client():
    """Create a FastAPI TestClient (lifespan is not triggered without the ``with`` block)."""
    return TestClient(app)


class TestListSessions:
    """Tests for GET /api/sessions."""

    def test_list_sessions_empty(self, client):
        """Should return an empty sessions list when no sessions exist."""
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        assert resp.json() == {"sessions": []}

    def test_list_sessions_with_multiple(self, client):
        """Should return all active sessions with correct fields (id, title, messages, last_active)."""
        _add_session("s1", "Chat A", [{"role": "user", "content": "hi"}])
        _add_session("s2", "Chat B", [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "world"}])

        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["sessions"]) == 2

        s1 = next(s for s in data["sessions"] if s["id"] == "s1")
        assert s1["title"] == "Chat A"
        assert s1["messages"] == 1
        assert "last_active" in s1

    def test_list_sessions_when_manager_none(self, client):
        """Should return an empty list when session_manager is None (503 fallback)."""
        import app.state as state

        state.session_manager = None
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        assert resp.json() == {"sessions": []}


class TestGetSessionMessages:
    """Tests for GET /api/sessions/{session_id}/messages."""

    def test_get_messages_existing_session(self, client):
        """Should return messages for an existing session."""
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]
        _add_session("s1", "Test", msgs)

        resp = client.get("/api/sessions/s1/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "s1"
        assert len(data["messages"]) == 2
        assert data["messages"][0]["content"] == "hello"

    def test_get_messages_new_session(self, client):
        """Should create and return an empty session for an unknown session_id."""
        resp = client.get("/api/sessions/new-session/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "new-session"
        assert data["messages"] == []

    def test_get_messages_with_query_results(self, client):
        """Should attach persisted _query_results metadata to the last assistant message."""
        import app.state as state

        msgs = [
            {"role": "user", "content": "show data"},
            {"role": "assistant", "content": "here is the data"},
        ]
        sess = _add_session("s1", "Test", msgs)
        sess.metadata["_query_results"] = [{"col": "val"}]

        resp = client.get("/api/sessions/s1/messages")
        assert resp.status_code == 200
        data = resp.json()
        assistant_msgs = [m for m in data["messages"] if m["role"] == "assistant"]
        assert assistant_msgs
        assert assistant_msgs[0].get("query_results") == [{"col": "val"}]

    def test_get_messages_when_manager_none(self, client):
        """Should return 503 when session_manager is None."""
        import app.state as state

        state.session_manager = None
        resp = client.get("/api/sessions/s1/messages")
        assert resp.status_code == 503


class TestRenameSession:
    """Tests for PATCH /api/sessions/{session_id}."""

    def test_rename_existing_session(self, client):
        """Should rename an existing session and persist the change."""
        _add_session("s1", "Old Title")

        resp = client.patch("/api/sessions/s1", json={"title": "New Title"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        import app.state as state

        assert state.session_manager._sessions["s1"].title == "New Title"

    def test_rename_nonexistent_session(self, client):
        """Should silently succeed when renaming a non-existent session."""
        resp = client.patch("/api/sessions/nonexistent", json={"title": "Noop"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_rename_when_manager_none(self, client):
        """Should return 503 when session_manager is None."""
        import app.state as state

        state.session_manager = None
        resp = client.patch("/api/sessions/s1", json={"title": "New"})
        assert resp.status_code == 503


class TestClearAllSessions:
    """Tests for POST /api/sessions/clear."""

    def test_clear_all_sessions(self, client):
        """Should clear all sessions and return the count of deleted sessions."""
        import app.state as state

        _add_session("s1", "A")
        _add_session("s2", "B")
        assert len(state.session_manager._sessions) == 2

        resp = client.post("/api/sessions/clear")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["deleted"] == 2
        assert len(state.session_manager._sessions) == 0

    def test_clear_empty_sessions(self, client):
        """Should return deleted=0 when there are no sessions."""
        resp = client.post("/api/sessions/clear")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "deleted": 0}

    def test_clear_when_manager_none(self, client):
        """Should return 503 when session_manager is None."""
        import app.state as state

        state.session_manager = None
        resp = client.post("/api/sessions/clear")
        assert resp.status_code == 503


class TestDeleteSession:
    """Tests for DELETE /api/sessions/{session_id}."""

    def test_delete_existing_session(self, client):
        """Should delete a specific session by its ID."""
        _add_session("s1", "A")
        resp = client.delete("/api/sessions/s1")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        import app.state as state

        assert "s1" not in state.session_manager._sessions

    def test_delete_nonexistent_session(self, client):
        """Should silently succeed when deleting a non-existent session."""
        resp = client.delete("/api/sessions/nonexistent")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_delete_when_manager_none(self, client):
        """Should return 503 when session_manager is None."""
        import app.state as state

        state.session_manager = None
        resp = client.delete("/api/sessions/s1")
        assert resp.status_code == 503
