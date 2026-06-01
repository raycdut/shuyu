"""Tests for app/persistence/token.py"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def setup_model():
    """Provide a mock config with a known model name."""
    import app.state as state
    state.config.llm.model = "gpt-4o-test"
    yield


class TestSaveTokenUsage:
    """Tests for save_token_usage."""

    def test_when_sqlite_is_none_does_not_crash(self):
        """Should return silently when _sqlite is None (no database attached)."""
        from app.persistence.token import save_token_usage
        import app.state as state

        state._sqlite = None
        state._configdb_session_factory = None
        save_token_usage(prompt=100, completion=50)

    def test_saves_data_correctly(self):
        """Should insert a row into token_usage with correct model/prompt/completion/total."""
        from app.persistence.token import save_token_usage
        from app.configdb.base import scoped_session
        from app.configdb.models.token import TokenUsage

        save_token_usage(prompt=200, completion=100)

        with scoped_session() as s:
            row = s.query(TokenUsage).first()
            assert row is not None
            assert row.model == "gpt-4o-test"
            assert row.prompt == 200
            assert row.completion == 100
            assert row.total == 300
            assert row.session_id is None

    def test_saves_with_session_id(self):
        """Should save the session_id when provided."""
        from app.persistence.token import save_token_usage
        from app.configdb.base import scoped_session
        from app.configdb.models.token import TokenUsage

        save_token_usage(prompt=50, completion=25, session_id="session-abc")

        with scoped_session() as s:
            row = s.query(TokenUsage).first()
            assert row.session_id == "session-abc"

    def test_handles_db_error_gracefully(self):
        """Should not crash when the token_usage table does not exist."""
        from app.persistence.token import save_token_usage
        from app.configdb.base import scoped_session
        from app.configdb.models.token import TokenUsage

        with scoped_session() as s:
            s.query(TokenUsage).delete()

        save_token_usage(prompt=100, completion=50)
