"""Tests for prompt management routes — list, get, upsert, activate, defaults."""

from __future__ import annotations

import time
import sqlite3
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(autouse=True)
def setup_db():
    """Set up an in-memory SQLite database with a prompts table before each test."""
    import app.state as state
    from app.config import Config

    state._sqlite = sqlite3.connect(":memory:", check_same_thread=False)
    state._sqlite.execute("PRAGMA journal_mode=WAL")
    state._sqlite.execute("""
        CREATE TABLE IF NOT EXISTS prompts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL DEFAULT 'default',
            content    TEXT NOT NULL,
            version    INTEGER NOT NULL DEFAULT 1,
            is_active  INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL
        )
    """)
    state.config = Config()
    yield
    if state._sqlite is not None:
        state._sqlite.close()
    state._sqlite = None


@pytest.fixture
def client():
    """Create a FastAPI TestClient."""
    return TestClient(app)


class TestListPrompts:
    """Tests for GET /api/prompts."""

    def test_list_prompts_empty(self, client):
        """Should return an empty prompts list when no prompts exist."""
        resp = client.get("/api/prompts")
        assert resp.status_code == 200
        data = resp.json()
        assert "prompts" in data
        assert data["prompts"] == []

    def test_list_prompts_with_category(self, client):
        """Should filter prompts by the given category name."""
        import app.state as state
        now = time.time()
        state._sqlite.execute(
            "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, 1, 1, ?)",
            ("system", "system prompt", now),
        )
        state._sqlite.commit()

        resp = client.get("/api/prompts?category=system")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["prompts"]) >= 1
        assert data["prompts"][0]["name"] == "system"

    def test_list_prompts_no_match(self, client):
        """Should return empty list when category filter matches no prompts."""
        import app.state as state
        now = time.time()
        state._sqlite.execute(
            "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, 1, 1, ?)",
            ("system", "system prompt", now),
        )
        state._sqlite.commit()

        resp = client.get("/api/prompts?category=sql_gen")
        assert resp.status_code == 200
        data = resp.json()
        assert data["prompts"] == []


class TestGetActivePrompts:
    """Tests for GET /api/prompts/active."""

    def test_get_active_prompts(self, client):
        """Should return active prompt per category, falling back to defaults."""
        import app.state as state
        now = time.time()
        state._sqlite.execute(
            "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, 1, 1, ?)",
            ("system", "active system prompt", now),
        )
        state._sqlite.commit()

        resp = client.get("/api/prompts/active")
        assert resp.status_code == 200
        data = resp.json()
        assert "system" in data
        assert data["system"]["content"] == "active system prompt"
        assert data["system"]["version"] == 1

        # Fallback categories should have id=None
        for cat in ["sql_gen", "plan", "plan_reflect", "report_reflect", "schema_describe"]:
            assert cat in data
            assert data[cat]["id"] is None

    def test_get_active_prompts_when_sqlite_none(self, client):
        """Should return None for all categories when _sqlite is None."""
        import app.state as state
        state._sqlite = None

        resp = client.get("/api/prompts/active")
        assert resp.status_code == 200
        data = resp.json()
        for cat in ["system", "sql_gen", "plan", "plan_reflect", "report_reflect", "schema_describe"]:
            assert data[cat] is None


class TestGetPromptById:
    """Tests for GET /api/prompts/{prompt_id}."""

    def test_get_prompt_by_id(self, client):
        """Should return the prompt details for a valid ID."""
        import app.state as state
        now = time.time()
        state._sqlite.execute(
            "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, 1, 1, ?)",
            ("system", "specific content", now),
        )
        state._sqlite.commit()
        prompt_id = state._sqlite.execute(
            "SELECT id FROM prompts WHERE name = 'system'"
        ).fetchone()[0]

        resp = client.get(f"/api/prompts/{prompt_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == prompt_id
        assert data["content"] == "specific content"
        assert data["name"] == "system"

    def test_get_prompt_not_found(self, client):
        """Should return an error for a non-existent prompt ID."""
        resp = client.get("/api/prompts/99999")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_get_prompt_when_sqlite_none(self, client):
        """Should return error when _sqlite is None."""
        import app.state as state
        state._sqlite = None

        resp = client.get("/api/prompts/1")
        assert resp.status_code == 200
        assert "error" in resp.json()


class TestGetDefaultPrompt:
    """Tests for GET /api/prompts/{category}/default."""

    def test_get_default_prompt(self, client):
        """Should return the hardcoded default prompt content for a valid category."""
        resp = client.get("/api/prompts/system/default")
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "system"
        assert "<instructions>" in data["content"]

    def test_get_default_prompt_unknown(self, client):
        """Should return an error for an unknown category."""
        resp = client.get("/api/prompts/unknown/default")
        assert resp.status_code == 200
        assert "error" in resp.json()


class TestUpsertPrompt:
    """Tests for PUT /api/prompts."""

    def test_create_prompt(self, client):
        """Should create a new prompt version."""
        resp = client.put("/api/prompts", json={
            "category": "system",
            "content": "new system prompt",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["version"] == 1

    def test_create_prompt_increments_version(self, client):
        """Should increment version number when creating a new version."""
        client.put("/api/prompts", json={
            "category": "sql_gen",
            "content": "version 1",
        })
        resp = client.put("/api/prompts", json={
            "category": "sql_gen",
            "content": "version 2",
        })
        assert resp.status_code == 200
        assert resp.json()["version"] == 2

    def test_upsert_with_legacy_name_field(self, client):
        """Should support the legacy 'name' field as an alias for 'category'."""
        resp = client.put("/api/prompts", json={
            "name": "plan",
            "content": "plan prompt",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True

    def test_upsert_when_sqlite_none(self, client):
        """Should return error when _sqlite is None."""
        import app.state as state
        state._sqlite = None

        resp = client.put("/api/prompts", json={
            "category": "system",
            "content": "content",
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is False


class TestActivatePrompt:
    """Tests for PATCH /api/prompts/{prompt_id}/activate."""

    def test_activate_prompt_version(self, client):
        """Should activate a specific prompt version and deactivate others in the same category."""
        import app.state as state
        now = time.time()
        state._sqlite.execute(
            "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, 1, 1, ?)",
            ("system", "v1", now),
        )
        state._sqlite.execute(
            "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, 2, 0, ?)",
            ("system", "v2", now + 1),
        )
        state._sqlite.commit()

        v1_id = state._sqlite.execute(
            "SELECT id FROM prompts WHERE name = 'system' AND version = 1"
        ).fetchone()[0]
        v2_id = state._sqlite.execute(
            "SELECT id FROM prompts WHERE name = 'system' AND version = 2"
        ).fetchone()[0]

        resp = client.patch(f"/api/prompts/{v2_id}/activate")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        v1_active = state._sqlite.execute(
            "SELECT is_active FROM prompts WHERE id = ?", (v1_id,)
        ).fetchone()[0]
        v2_active = state._sqlite.execute(
            "SELECT is_active FROM prompts WHERE id = ?", (v2_id,)
        ).fetchone()[0]
        assert v1_active == 0
        assert v2_active == 1

    def test_activate_nonexistent(self, client):
        """Should return ok=False when activating a non-existent prompt ID."""
        resp = client.patch("/api/prompts/9999/activate")
        assert resp.status_code == 200
        assert resp.json()["ok"] is False

    def test_activate_when_sqlite_none(self, client):
        """Should return error when _sqlite is None."""
        import app.state as state
        state._sqlite = None

        resp = client.patch("/api/prompts/1/activate")
        assert resp.status_code == 200
        assert resp.json()["ok"] is False
