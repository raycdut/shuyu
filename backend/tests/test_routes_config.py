"""Tests for prompt management routes — list, get, upsert, activate, defaults."""

from __future__ import annotations

import time
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Create a FastAPI TestClient."""
    return TestClient(app)


class TestListPrompts:
    """Tests for GET /api/prompts."""

    def test_list_prompts_not_empty(self, client):
        """Should return prompts list (seeded by default)."""
        resp = client.get("/api/prompts")
        assert resp.status_code == 200
        data = resp.json()
        assert "prompts" in data
        assert len(data["prompts"]) >= 10

    def test_list_prompts_with_category(self, client):
        """Should filter prompts by the given category name."""
        resp = client.get("/api/prompts?category=system")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["prompts"]) >= 1
        assert data["prompts"][0]["name"] == "system"

    def test_list_prompts_no_match(self, client):
        """Should return empty list when category filter matches no prompts."""
        resp = client.get("/api/prompts?category=__nonexistent_cat__")
        assert resp.status_code == 200
        data = resp.json()
        assert data["prompts"] == []


class TestGetActivePrompts:
    """Tests for GET /api/prompts/active."""

    def test_get_active_prompts(self, client):
        """Should return active prompt per category, falling back to defaults."""
        from app.configdb.base import scoped_session
        from app.configdb.models.prompt import Prompt
        with scoped_session() as s:
            # Insert a higher-version prompt for an existing category
            existing = s.query(Prompt).filter_by(name="exec_freeform", is_active=1).first()
            if existing:
                existing.is_active = 0
            s.add(Prompt(name="exec_freeform", content="active test prompt", version=2, is_active=1, created_at=time.time()))

        resp = client.get("/api/prompts/active")
        assert resp.status_code == 200
        data = resp.json()
        assert "exec_freeform" in data
        assert data["exec_freeform"]["content"] == "active test prompt"
        assert data["exec_freeform"]["version"] == 2

        for cat in ["plan", "plan_reflect", "report_reflect", "schema_describe"]:
            assert cat in data
            assert cat in data
            assert data[cat].get("id") is not None
            assert data[cat].get("content") is not None

    def test_get_active_prompts_when_sqlite_none(self, client):
        """Should return defaults for all categories when DB is unavailable."""
        import app.state as state
        old_sqlite = state._sqlite
        old_factory = state._configdb_session_factory
        state._sqlite = None
        state._configdb_session_factory = None

        resp = client.get("/api/prompts/active")
        assert resp.status_code == 200
        data = resp.json()
        for cat in ["system", "sql_gen", "plan", "plan_reflect", "report_reflect", "schema_describe"]:
            assert data[cat]["id"] is None
            assert data[cat]["content"] is not None

        state._sqlite = old_sqlite
        state._configdb_session_factory = old_factory


class TestGetPromptById:
    """Tests for GET /api/prompts/{prompt_id}."""

    def test_get_prompt_by_id(self, client):
        """Should return the prompt details for a valid ID."""
        from app.configdb.base import scoped_session
        from app.configdb.models.prompt import Prompt
        with scoped_session() as s:
            s.add(Prompt(name="test_custom", content="specific content", version=1, is_active=1, created_at=time.time()))
            prompt_id = s.query(Prompt).filter_by(name="test_custom").first().id

        resp = client.get(f"/api/prompts/{prompt_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == prompt_id
        assert data["content"] == "specific content"
        assert data["name"] == "test_custom"

    def test_get_prompt_not_found(self, client):
        """Should return an error for a non-existent prompt ID."""
        resp = client.get("/api/prompts/99999")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_get_prompt_when_sqlite_none(self, client):
        """Should return error when DB is unavailable."""
        import app.state as state
        old_sqlite = state._sqlite
        old_factory = state._configdb_session_factory
        state._sqlite = None
        state._configdb_session_factory = None

        resp = client.get("/api/prompts/1")
        assert resp.status_code == 200
        assert "error" in resp.json()

        state._sqlite = old_sqlite
        state._configdb_session_factory = old_factory


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
            "category": "test_new_cat",
            "content": "new prompt",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["version"] == 1

    def test_create_prompt_increments_version(self, client):
        """Should increment version number when creating a new version."""
        client.put("/api/prompts", json={
            "category": "test_ver_cat",
            "content": "version 1",
        })
        resp = client.put("/api/prompts", json={
            "category": "test_ver_cat",
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
        """Should return error when DB is unavailable."""
        import app.state as state
        old_sqlite = state._sqlite
        old_factory = state._configdb_session_factory
        state._sqlite = None
        state._configdb_session_factory = None

        resp = client.put("/api/prompts", json={
            "category": "system",
            "content": "content",
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is False

        state._sqlite = old_sqlite
        state._configdb_session_factory = old_factory


class TestActivatePrompt:
    """Tests for PATCH /api/prompts/{prompt_id}/activate."""

    def test_activate_prompt_version(self, client):
        """Should activate a specific prompt version and deactivate others in the same category."""
        from app.configdb.base import scoped_session
        from app.configdb.models.prompt import Prompt
        with scoped_session() as s:
            s.add(Prompt(name="test_act_cat", content="v1", version=1, is_active=1, created_at=time.time()))
            s.add(Prompt(name="test_act_cat", content="v2", version=2, is_active=0, created_at=time.time() + 1))

        with scoped_session() as s:
            v1 = s.query(Prompt).filter_by(name="test_act_cat", version=1).first()
            v2 = s.query(Prompt).filter_by(name="test_act_cat", version=2).first()

        resp = client.patch(f"/api/prompts/{v2.id}/activate")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        with scoped_session() as s:
            v1_check = s.query(Prompt).filter_by(id=v1.id).first()
            v2_check = s.query(Prompt).filter_by(id=v2.id).first()
            assert v1_check.is_active == 0
            assert v2_check.is_active == 1

    def test_activate_nonexistent(self, client):
        """Should return ok=False when activating a non-existent prompt ID."""
        resp = client.patch("/api/prompts/9999/activate")
        assert resp.status_code == 200
        assert resp.json()["ok"] is False

    def test_activate_when_sqlite_none(self, client):
        """Should return error when DB is unavailable."""
        import app.state as state
        old_sqlite = state._sqlite
        old_factory = state._configdb_session_factory
        state._sqlite = None
        state._configdb_session_factory = None

        resp = client.patch("/api/prompts/1/activate")
        assert resp.status_code == 200
        assert resp.json()["ok"] is False

        state._sqlite = old_sqlite
        state._configdb_session_factory = old_factory
