"""Tests for app/persistence/token.py"""

from __future__ import annotations

import sqlite3
import time

import pytest


@pytest.fixture(autouse=True)
def setup_db():
    """Set up an in-memory SQLite database with token_usage table and a mock config."""
    import app.state as state

    # Create in-memory SQLite
    state._sqlite = sqlite3.connect(":memory:")
    state._sqlite.execute("PRAGMA journal_mode=WAL")
    state._sqlite.execute("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            model      TEXT NOT NULL,
            prompt     INTEGER NOT NULL DEFAULT 0,
            completion INTEGER NOT NULL DEFAULT 0,
            total      INTEGER NOT NULL DEFAULT 0,
            session_id TEXT,
            created_at REAL NOT NULL
        )
    """)

    # Provide a mock config with a known model name
    from app.config import Config

    state.config = Config()
    state.config.llm.model = "gpt-4o-test"

    yield

    if state._sqlite is not None:
        state._sqlite.close()
    state._sqlite = None


class TestSaveTokenUsage:
    """Tests for save_token_usage."""

    def test_when_sqlite_is_none_does_not_crash(self):
        """Should return silently when _sqlite is None (no database attached)."""
        from app.persistence.token import save_token_usage
        import app.state as state

        state._sqlite = None
        # This should not raise any exception
        save_token_usage(prompt=100, completion=50)

    def test_saves_data_correctly(self):
        """Should insert a row into token_usage with correct model/prompt/completion/total."""
        from app.persistence.token import save_token_usage

        save_token_usage(prompt=200, completion=100)

        import app.state as state

        row = state._sqlite.execute(
            "SELECT model, prompt, completion, total, session_id FROM token_usage"
        ).fetchone()
        assert row is not None
        assert row[0] == "gpt-4o-test"
        assert row[1] == 200
        assert row[2] == 100
        assert row[3] == 300  # 200 + 100
        assert row[4] is None  # no session_id

    def test_saves_with_session_id(self):
        """Should save the session_id when provided."""
        from app.persistence.token import save_token_usage

        save_token_usage(prompt=50, completion=25, session_id="session-abc")

        import app.state as state

        row = state._sqlite.execute(
            "SELECT session_id FROM token_usage"
        ).fetchone()
        assert row[0] == "session-abc"

    def test_handles_db_error_gracefully(self):
        """Should not crash when the token_usage table does not exist."""
        from app.persistence.token import save_token_usage
        import app.state as state

        # Drop the table to simulate a missing table error
        state._sqlite.execute("DROP TABLE token_usage")
        state._sqlite.commit()

        # This should not raise any exception
        save_token_usage(prompt=100, completion=50)
