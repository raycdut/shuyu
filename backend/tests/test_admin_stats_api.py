"""Tests for admin dashboard statistics API."""

from __future__ import annotations

import json
import time
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.auth.service import init_auth_config, create_user, create_token
from app.configdb.base import scoped_session
from app.configdb.models.session import Session as SessionModel, Message
from app.configdb.models.token import TokenUsage


def seed_test_data() -> dict:
    """Seed test data into ConfigDB. Returns admin user dict."""
    now = time.time()
    today_start_iso = datetime(
        datetime.now(timezone.utc).year,
        datetime.now(timezone.utc).month,
        datetime.now(timezone.utc).day,
        tzinfo=timezone.utc,
    ).isoformat()

    admin = create_user("admin", "admin123")
    user2 = create_user("alice", "pass123")
    user3 = create_user("bob", "pass456")
    user4 = create_user("charlie", "pass789")

    from app.configdb.models.user import User
    with scoped_session() as s:
        for uid in [admin["id"], user2["id"]]:
            user = s.query(User).filter_by(id=uid).first()
            if user:
                user.last_login_at = today_start_iso

        session1 = "sess-001"
        session2 = "sess-002"
        session3 = "sess-003"

        for sid, uid in [(session1, admin["id"]), (session2, user2["id"]), (session3, user3["id"])]:
            s.add(SessionModel(
                id=sid, title="test session", created_at=now, updated_at=now, user_id=uid,
            ))

        msg_time_today = now
        msg_time_yesterday = now - 86400
        msg_time_2days_ago = now - 172800

        for i in range(3):
            s.add(Message(session_id=session1, role="user", content=f"Question {i+1}", created_at=msg_time_today))
        for i in range(5):
            s.add(Message(session_id=session2, role="user", content=f"Alice Q {i+1}", created_at=msg_time_today))
        for i in range(2):
            s.add(Message(session_id=session3, role="user", content=f"Bob Q {i+1}", created_at=msg_time_yesterday))
        for i in range(3):
            s.add(Message(session_id=session1, role="assistant", content=f"Answer {i+1}", created_at=msg_time_today))

        s.add(TokenUsage(model="gpt-4o", prompt=100, completion=200, total=300, session_id=session1, created_at=msg_time_today))
        s.add(TokenUsage(model="gpt-4o", prompt=150, completion=250, total=400, session_id=session2, created_at=msg_time_today))
        s.add(TokenUsage(model="claude-3", prompt=200, completion=300, total=500, session_id=session3, created_at=msg_time_yesterday))
        s.add(TokenUsage(model="gpt-4o", prompt=50, completion=80, total=130, session_id=session3, created_at=msg_time_2days_ago))

    return admin


@pytest.fixture
def client():
    import app.state as state
    from unittest import mock

    init_auth_config()
    state.config.llm.api_key = "test-key"
    state.config.llm.api_base = "https://test.api.com"
    state.config.llm.timeout = 60
    state.config.llm.model = "gpt-4o"
    state.config.llm.provider = "openai"

    patchers = [
        mock.patch("app.main.init_configdb", return_value=None),
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

    def test_get_stats_returns_all_sections(self, client):
        """GET /api/admin/stats should return overview, trends, top_users, model_usage."""
        admin = seed_test_data()
        token = create_token(admin)
        resp = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert "overview" in data
        assert "trends" in data
        assert "top_users" in data
        assert "model_usage" in data

        overview = data["overview"]
        assert overview["total_users"] >= 4
        assert overview["total_sessions"] >= 3
        assert overview["total_messages"] >= 13
        assert overview["today_logins"] >= 2
        assert overview["today_questions"] > 0
        assert overview["today_token_total"] > 0

    def test_overview_counts_are_correct(self, client):
        """Verify specific counts match seeded data."""
        admin = seed_test_data()
        token = create_token(admin)
        resp = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        overview = data["overview"]

        assert overview["total_users"] == 4
        assert overview["total_sessions"] == 3
        assert overview["total_messages"] == 13
        assert overview["today_logins"] == 2

        assert overview["today_questions"] == 8  # 3 + 5 from today
        assert overview["today_token_total"] == 700  # 300 + 400 from today

    def test_trends_data_structure(self, client):
        """Verify trends contain correct date ranges and data points."""
        admin = seed_test_data()
        token = create_token(admin)
        resp = client.get("/api/admin/stats?days=7", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        trends = data["trends"]

        assert len(trends["active_users"]) == 7
        assert len(trends["questions"]) == 7
        assert len(trends["token_usage"]) == 7

        assert trends["active_users"][0]["date"] <= trends["active_users"][-1]["date"]
        assert all(isinstance(p["value"], int) for p in trends["active_users"])

    def test_top_users_ordered_by_question_count(self, client):
        """Verify top_users are sorted descending by question count."""
        admin = seed_test_data()
        token = create_token(admin)
        resp = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        top = data["top_users"]

        assert len(top) > 0
        assert top[0]["username"] == "alice"
        assert top[0]["question_count"] == 5
        assert top[1]["username"] == "admin"
        assert top[1]["question_count"] == 3

    def test_model_usage_aggregation(self, client):
        """Verify model_usage groups by model and sums correctly."""
        admin = seed_test_data()
        token = create_token(admin)
        resp = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        model_usage = data["model_usage"]

        models = {m["model"]: m for m in model_usage}
        assert "gpt-4o" in models
        assert "claude-3" in models

        gpt = models["gpt-4o"]
        assert gpt["prompt_tokens"] == 300    # 100 + 150 + 50
        assert gpt["completion_tokens"] == 530  # 200 + 250 + 80
        assert gpt["total_tokens"] == 830     # 300 + 400 + 130
        assert gpt["call_count"] == 3

        claude = models["claude-3"]
        assert claude["call_count"] == 1
        assert claude["total_tokens"] == 500

    def test_unauthenticated_access_returns_401(self, client):
        """Verify unauthenticated request gets 401."""
        resp = client.get("/api/admin/stats")
        assert resp.status_code == 401
