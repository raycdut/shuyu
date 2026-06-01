import pytest
import time
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


class TestPromptPersistence:
    def test_seed_prompts(self):
        from app.persistence import PROMPT_DEFAULTS, _get_default_prompt_content
        assert len(PROMPT_DEFAULTS) == 10
        assert "system" in PROMPT_DEFAULTS
        assert "sql_gen" in PROMPT_DEFAULTS
        assert "plan" in PROMPT_DEFAULTS
        assert "plan_reflect" in PROMPT_DEFAULTS
        assert "report_reflect" in PROMPT_DEFAULTS
        assert "schema_describe" in PROMPT_DEFAULTS

    def test_get_default_prompt_content(self):
        from app.persistence import _get_default_prompt_content
        content = _get_default_prompt_content("system")
        assert content is not None
        assert "<instructions>" in content
        assert _get_default_prompt_content("unknown") is None

    def test_migrate_default_to_system(self):
        from app.configdb import _migrate_prompt_names
        from app.configdb.base import scoped_session
        from app.configdb.models.prompt import Prompt

        with scoped_session() as s:
            s.add(Prompt(name="default", content="old content", version=1, is_active=1, created_at=time.time()))

        _migrate_prompt_names()

        with scoped_session() as s:
            default_count = s.query(Prompt).filter_by(name="default").count()
            system_count = s.query(Prompt).filter_by(name="system").count()
            assert default_count == 0
            assert system_count >= 2
            # "old content" should be the latest version (merged into system)
            latest = s.query(Prompt).filter_by(name="system").order_by(Prompt.version.desc()).first()
            assert latest.content == "old content"

    def test_migrate_merge_default_into_existing_system(self):
        from app.configdb import _migrate_prompt_names
        from app.configdb.base import scoped_session
        from app.configdb.models.prompt import Prompt

        with scoped_session() as s:
            s.add(Prompt(name="system", content="existing system", version=1, is_active=1, created_at=time.time()))
            s.add(Prompt(name="default", content="old default", version=1, is_active=0, created_at=time.time() + 1))

        _migrate_prompt_names()

        with scoped_session() as s:
            default_count = s.query(Prompt).filter_by(name="default").count()
            assert default_count == 0
            rows = s.query(Prompt).filter_by(name="system").order_by(Prompt.version).all()
            contents = [r.content for r in rows]
            assert "existing system" in contents
            assert "old default" in contents


class TestPromptAPI:
    def test_list_prompts_empty(self, client):
        resp = client.get("/api/prompts")
        assert resp.status_code == 200
        data = resp.json()
        assert "prompts" in data

    def test_list_prompts_with_category(self, client):
        from app.configdb.base import scoped_session
        from app.configdb.models.prompt import Prompt
        with scoped_session() as s:
            s.add(Prompt(name="system", content="test prompt", version=1, is_active=1, created_at=time.time()))

        resp = client.get("/api/prompts?category=system")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["prompts"]) >= 1
        assert data["prompts"][0]["name"] == "system"

    def test_create_prompt(self, client):
        resp = client.put("/api/prompts", json={
            "category": "my_custom_prompt",
            "content": "new custom prompt",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["version"] == 1

    def test_create_prompt_increments_version(self, client):
        client.put("/api/prompts", json={
            "category": "test_ver_cat",
            "content": "version 1",
        })
        resp = client.put("/api/prompts", json={
            "category": "test_ver_cat",
            "content": "version 2",
        })
        assert resp.json()["version"] == 2

    def test_get_prompt_by_id(self, client):
        from app.configdb.base import scoped_session
        from app.configdb.models.prompt import Prompt
        with scoped_session() as s:
            s.add(Prompt(name="test_custom", content="test content", version=1, is_active=1, created_at=time.time()))
            prompt_id = s.query(Prompt).filter_by(name="test_custom").first().id

        resp = client.get(f"/api/prompts/{prompt_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "test content"
        assert data["name"] == "test_custom"

    def test_activate_prompt_version(self, client):
        from app.configdb.base import scoped_session
        from app.configdb.models.prompt import Prompt
        with scoped_session() as s:
            s.add(Prompt(name="system", content="v1", version=1, is_active=1, created_at=time.time()))
            s.add(Prompt(name="system", content="v2", version=2, is_active=0, created_at=time.time() + 1))

        with scoped_session() as s:
            v1 = s.query(Prompt).filter_by(name="system", version=1).first()
            v2 = s.query(Prompt).filter_by(name="system", version=2).first()

        resp = client.patch(f"/api/prompts/{v2.id}/activate")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        with scoped_session() as s:
            assert s.query(Prompt).filter_by(id=v1.id).first().is_active == 0
            assert s.query(Prompt).filter_by(id=v2.id).first().is_active == 1

    def test_activate_nonexistent(self, client):
        resp = client.patch("/api/prompts/9999/activate")
        assert resp.status_code == 200
        assert resp.json()["ok"] is False

    def test_get_active_prompts(self, client):
        from app.configdb.base import scoped_session
        from app.configdb.models.prompt import Prompt
        with scoped_session() as s:
            existing = s.query(Prompt).filter_by(name="exec_freeform", is_active=1).first()
            if existing:
                existing.is_active = 0
            s.add(Prompt(name="exec_freeform", content="active test content", version=2, is_active=1, created_at=time.time()))

        resp = client.get("/api/prompts/active")
        assert resp.status_code == 200
        data = resp.json()
        assert "exec_freeform" in data
        assert data["exec_freeform"]["content"] == "active test content"
        assert data["exec_freeform"]["version"] == 2
        assert "sql_gen" in data
        assert data["sql_gen"]["id"] is not None

    def test_get_default_prompt(self, client):
        resp = client.get("/api/prompts/system/default")
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "system"
        assert "<instructions>" in data["content"]

    def test_get_default_prompt_unknown(self, client):
        resp = client.get("/api/prompts/unknown/default")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_upsert_with_legacy_name(self, client):
        resp = client.put("/api/prompts", json={
            "name": "plan",
            "content": "legacy plan prompt",
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
