import pytest
import sqlite3
import time
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def setup_db():
    import app.state as state
    state._sqlite = sqlite3.connect(":memory:", check_same_thread=False)
    state._sqlite.execute("PRAGMA journal_mode=WAL")
    state._sqlite.execute("""
        CREATE TABLE IF NOT EXISTS prompts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL DEFAULT 'default',
            content    TEXT NOT NULL,
            version    INTEGER NOT NULL DEFAULT 1,
            is_active  INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL
        )
    """)
    from app.config import Config
    state.config = Config()
    yield
    state._sqlite.close()
    state._sqlite = None


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


class TestPromptPersistence:
    def test_seed_prompts(self):
        from app.persistence import PROMPT_DEFAULTS, _get_default_prompt_content
        assert len(PROMPT_DEFAULTS) == 6
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
        import app.state as state
        now = time.time()
        state._sqlite.execute(
            "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, 1, 1, ?)",
            ("default", "old content", now),
        )
        state._sqlite.commit()

        from app.persistence import _migrate_prompt_names
        _migrate_prompt_names()

        default_count = state._sqlite.execute(
            "SELECT COUNT(*) FROM prompts WHERE name = 'default'"
        ).fetchone()[0]
        system_count = state._sqlite.execute(
            "SELECT COUNT(*) FROM prompts WHERE name = 'system'"
        ).fetchone()[0]
        assert default_count == 0
        assert system_count >= 1
        content = state._sqlite.execute(
            "SELECT content FROM prompts WHERE name = 'system'"
        ).fetchone()[0]
        assert content == "old content"

    def test_migrate_merge_default_into_existing_system(self):
        import app.state as state
        now = time.time()
        state._sqlite.execute(
            "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, 1, 1, ?)",
            ("system", "existing system", now),
        )
        state._sqlite.execute(
            "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, 1, 0, ?)",
            ("default", "old default", now + 1),
        )
        state._sqlite.commit()

        from app.persistence import _migrate_prompt_names
        _migrate_prompt_names()

        default_count = state._sqlite.execute(
            "SELECT COUNT(*) FROM prompts WHERE name = 'default'"
        ).fetchone()[0]
        assert default_count == 0
        rows = state._sqlite.execute(
            "SELECT content, version FROM prompts WHERE name = 'system' ORDER BY version"
        ).fetchall()
        contents = [r[0] for r in rows]
        assert "existing system" in contents
        assert "old default" in contents


class TestPromptAPI:
    def test_list_prompts_empty(self, client):
        resp = client.get("/api/prompts")
        assert resp.status_code == 200
        data = resp.json()
        assert "prompts" in data

    def test_list_prompts_with_category(self, client):
        import app.state as state
        now = time.time()
        state._sqlite.execute(
            "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, 1, 1, ?)",
            ("system", "test prompt", now),
        )
        state._sqlite.commit()

        resp = client.get("/api/prompts?category=system")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["prompts"]) >= 1
        assert data["prompts"][0]["name"] == "system"

    def test_create_prompt(self, client):
        resp = client.put("/api/prompts", json={
            "category": "system",
            "content": "new system prompt",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["version"] == 1

    def test_create_prompt_increments_version(self, client):
        client.put("/api/prompts", json={
            "category": "sql_gen",
            "content": "version 1",
        })
        resp = client.put("/api/prompts", json={
            "category": "sql_gen",
            "content": "version 2",
        })
        assert resp.json()["version"] == 2

    def test_get_prompt_by_id(self, client):
        import app.state as state
        now = time.time()
        state._sqlite.execute(
            "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, 1, 1, ?)",
            ("system", "test content", now),
        )
        state._sqlite.commit()
        row = state._sqlite.execute("SELECT id FROM prompts WHERE name = 'system'").fetchone()
        prompt_id = row[0]

        resp = client.get(f"/api/prompts/{prompt_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "test content"
        assert data["name"] == "system"

    def test_activate_prompt_version(self, client):
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
        resp = client.patch("/api/prompts/9999/activate")
        assert resp.status_code == 200
        assert resp.json()["ok"] is False

    def test_get_active_prompts(self, client):
        import app.state as state
        now = time.time()
        state._sqlite.execute(
            "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, 1, 1, ?)",
            ("system", "active system", now),
        )
        state._sqlite.commit()

        resp = client.get("/api/prompts/active")
        assert resp.status_code == 200
        data = resp.json()
        assert "system" in data
        assert data["system"]["content"] == "active system"
        assert data["system"]["version"] == 1
        assert "sql_gen" in data
        assert data["sql_gen"]["id"] is None  # fallback to default

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
