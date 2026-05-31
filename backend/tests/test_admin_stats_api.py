"""Tests for admin dashboard statistics API."""

from __future__ import annotations

import json
import time
import sqlite3
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.auth.service import init_auth_config, create_user, create_token


def _init_in_memory_db():
    """Create an in-memory SQLite DB with all required tables and set it on state.

    Uses check_same_thread=False so the same connection works across TestClient threads.
    """
    import app.state as state
    sql = sqlite3.connect(":memory:", check_same_thread=False)
    sql.execute("PRAGMA journal_mode=WAL")
    sql.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            TEXT PRIMARY KEY,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'user'
                          CHECK(role IN ('admin', 'user')),
            is_active     INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
            last_login_at TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id         TEXT PRIMARY KEY,
            title      TEXT DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            user_id    TEXT REFERENCES users(id)
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
        CREATE TABLE IF NOT EXISTS config_changelog (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            config_type TEXT NOT NULL,
            user_id     TEXT,
            changed_by  TEXT NOT NULL,
            summary     TEXT NOT NULL,
            diff        TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    state._sqlite = sql
    # Seed a prompt so the lifespan can load prompts
    import time as _time
    sql.execute(
        "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, 1, 1, ?)",
        ("system", "You are a helpful data analyst.", _time.time()),
    )
    sql.commit()


def get_sql() -> sqlite3.Connection | None:
    import app.state as state
    return state._sqlite


def seed_test_data() -> dict:
    """Seed test data into state._sqlite database. Returns admin user dict."""
    import app.state as state
    sql = state._sqlite
    now = time.time()

    admin = create_user("admin", "admin123")
    user2 = create_user("alice", "pass123")
    user3 = create_user("bob", "pass456")
    user4 = create_user("charlie", "pass789")

    today_start_iso = datetime(datetime.now(timezone.utc).year, datetime.now(timezone.utc).month, datetime.now(timezone.utc).day, tzinfo=timezone.utc).isoformat()
    for uid in [admin["id"], user2["id"]]:
        sql.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (today_start_iso, uid))

    session1 = "sess-001"
    session2 = "sess-002"
    session3 = "sess-003"

    for sid, uid in [(session1, admin["id"]), (session2, user2["id"]), (session3, user3["id"])]:
        sql.execute(
            "INSERT INTO sessions (id, title, created_at, updated_at, user_id) VALUES (?, ?, ?, ?, ?)",
            (sid, "test session", now, now, uid),
        )
    sql.commit()

    msg_time_today = now
    msg_time_yesterday = now - 86400
    msg_time_2days_ago = now - 172800

    for i in range(3):
        sql.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
            (session1, f"Question {i+1}", msg_time_today),
        )
    for i in range(5):
        sql.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
            (session2, f"Alice Q {i+1}", msg_time_today),
        )
    for i in range(2):
        sql.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
            (session3, f"Bob Q {i+1}", msg_time_yesterday),
        )
    for i in range(3):
        sql.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, 'assistant', ?, ?)",
            (session1, f"Answer {i+1}", msg_time_today),
        )
    sql.commit()

    sql.execute(
        "INSERT INTO token_usage (model, prompt, completion, total, session_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("gpt-4o", 100, 200, 300, session1, msg_time_today),
    )
    sql.execute(
        "INSERT INTO token_usage (model, prompt, completion, total, session_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("gpt-4o", 150, 250, 400, session2, msg_time_today),
    )
    sql.execute(
        "INSERT INTO token_usage (model, prompt, completion, total, session_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("claude-3", 200, 300, 500, session3, msg_time_yesterday),
    )
    sql.execute(
        "INSERT INTO token_usage (model, prompt, completion, total, session_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("gpt-4o", 50, 80, 130, session3, msg_time_2days_ago),
    )
    sql.commit()

    return admin


@pytest.fixture
def client():
    import app.state as state
    from app.config import Config
    from unittest import mock

    init_auth_config()
    state.config = Config()
    state.config.llm.api_key = "test-key"
    state.config.llm.api_base = "https://test.api.com"
    state.config.llm.timeout = 60
    state.config.llm.model = "gpt-4o"
    state.config.llm.provider = "openai"

    _init_in_memory_db()

    # Patch lifespan-dependent functions so they don't overwrite our pre-set state
    patchers = [
        mock.patch("app.main.init_sqlite", return_value=None),
        mock.patch("app.main.load_config_sqlite", return_value=None),
        mock.patch("app.main.load_db_connections_sqlite", return_value=None),
        mock.patch("app.main.load_config", return_value=state.config),
    ]
    for p in patchers:
        p.start()
    with TestClient(app) as c:
        yield c
    for p in patchers:
        p.stop()


class TestAdminStatsAPI:
    def test_unauthenticated_access_returns_401(self, client):
        resp = client.get("/api/admin/stats")
        assert resp.status_code == 401

    def test_get_stats_returns_all_sections(self, client):
        admin = seed_test_data()
        token = create_token(admin)
        resp = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "overview" in data
        assert "trends" in data
        assert "top_users" in data
        assert "model_usage" in data

    def test_overview_counts(self, client):
        admin = seed_test_data()
        token = create_token(admin)
        resp = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        overview = data["overview"]

        assert overview["total_users"] == 4
        assert overview["total_sessions"] == 3
        assert overview["total_messages"] == 13
        assert overview["today_logins"] == 2
        assert overview["today_questions"] == 8
        assert overview["today_token_total"] >= 700

    def test_trends_returns_7_days(self, client):
        admin = seed_test_data()
        token = create_token(admin)
        resp = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert len(data["trends"]["active_users"]) == 7
        assert len(data["trends"]["questions"]) == 7
        assert len(data["trends"]["token_usage"]) == 7

    def test_top_users_ordered(self, client):
        admin = seed_test_data()
        token = create_token(admin)
        resp = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert len(data["top_users"]) > 0
        assert data["top_users"][0]["username"] == "alice"
        assert data["top_users"][0]["question_count"] == 5

    def test_model_usage(self, client):
        admin = seed_test_data()
        token = create_token(admin)
        resp = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        assert len(data["model_usage"]) >= 2
        gpt4o = next(m for m in data["model_usage"] if m["model"] == "gpt-4o")
        assert gpt4o["call_count"] >= 3
        assert gpt4o["total_tokens"] >= 830

    def test_non_admin_returns_403(self, client):
        sql = get_sql()
        import uuid
        user_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        sql.execute(
            "INSERT INTO users (id, username, password_hash, role, is_active, created_at, updated_at) VALUES (?, ?, ?, 'user', 1, ?, ?)",
            (user_id, "regular_user", "hash", now_iso, now_iso),
        )
        sql.commit()
        from app.auth.service import get_user_by_id
        user = get_user_by_id(user_id)
        token = create_token(user)
        resp = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_custom_days_param(self, client):
        admin = seed_test_data()
        token = create_token(admin)
        resp = client.get("/api/admin/stats?days=3", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["trends"]["active_users"]) == 3
