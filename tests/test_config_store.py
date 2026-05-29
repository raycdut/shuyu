"""Tests for config_store.py — SQLite persistence with :memory:."""

from __future__ import annotations

import pytest

from app.config import Config
from app.config_store import (
    init_sqlite,
    load_config_sqlite,
    save_config_sqlite,
    load_db_connections_sqlite,
    save_db_connections_sqlite,
)


@pytest.fixture(autouse=True)
def setup_state():
    """Set up state module with fresh Config for each test."""
    from app import state
    state.config = Config()
    state._sqlite = None
    state._db_connections = []
    yield
    # Cleanup
    if state._sqlite:
        state._sqlite.close()
        state._sqlite = None


@pytest.fixture
def sqlite_db(setup_state):
    """Initialize SQLite :memory: and return the connection."""
    from app import state
    # Override storage path to :memory:
    state.config.storage.path = ":memory:"
    init_sqlite()
    assert state._sqlite is not None
    return state._sqlite


class TestInitSQLite:
    def test_tables_created(self, sqlite_db):
        """Should create all required tables."""
        tables = sqlite_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [r[0] for r in tables]
        assert "databases" in names
        assert "llm_providers" in names
        assert "messages" in names
        assert "sessions" in names
        assert "settings" in names

    def test_default_settings_inserted(self, sqlite_db):
        """Should insert default safety settings."""
        row = sqlite_db.execute("SELECT value FROM settings WHERE key='safety_read_only'").fetchone()
        assert row is not None
        assert row[0] == "true"

        row = sqlite_db.execute("SELECT value FROM settings WHERE key='safety_max_rows'").fetchone()
        assert row is not None
        assert row[0] == "1000"


class TestConfigPersistence:
    def test_save_and_load_llm_config(self, sqlite_db):
        from app import state
        state.config.llm.provider = "deepseek"
        state.config.llm.model = "deepseek-v4-flash"
        state.config.llm.api_key = "sk-test"
        state.config.llm.api_base = "https://api.deepseek.com"

        save_config_sqlite()

        # Reset and reload
        state.config.llm = state.config.llm.__class__()
        load_config_sqlite()

        assert state.config.llm.provider == "deepseek"
        assert state.config.llm.model == "deepseek-v4-flash"
        assert state.config.llm.api_key == "sk-test"
        assert state.config.llm.api_base == "https://api.deepseek.com"

    def test_save_and_load_safety_config(self, sqlite_db):
        from app import state
        state.config.safety.read_only = False
        state.config.safety.max_rows = 500

        save_config_sqlite()

        state.config.safety = state.config.safety.__class__()
        load_config_sqlite()

        assert state.config.safety.read_only is False
        assert state.config.safety.max_rows == 500

    def test_update_existing_llm_provider(self, sqlite_db):
        from app import state
        # First save
        state.config.llm.provider = "openai"
        state.config.llm.model = "gpt-4o"
        save_config_sqlite()

        # Then update
        state.config.llm.provider = "anthropic"
        state.config.llm.model = "claude-3"
        save_config_sqlite()

        # Reload
        state.config.llm = state.config.llm.__class__()
        load_config_sqlite()
        assert state.config.llm.provider == "anthropic"
        assert state.config.llm.model == "claude-3"


class TestDBConnectionsPersistence:
    def test_save_and_load(self, sqlite_db):
        from app import state
        state._db_connections = [
            {"id": "db1", "name": "TestDB", "type": "duckdb", "path": "/tmp/test.db",
             "connection_string": "", "host": "", "port": 0, "user": "", "password": "",
             "database": "", "include_tables": None, "exclude_tables": None, "is_active": False},
        ]
        save_db_connections_sqlite()

        state._db_connections = []
        load_db_connections_sqlite()
        assert len(state._db_connections) == 1
        assert state._db_connections[0]["name"] == "TestDB"

    def test_save_and_load_with_filters(self, sqlite_db):
        from app import state
        state._db_connections = [
            {"id": "db2", "name": "FilteredDB", "type": "duckdb", "path": "/tmp/db",
             "connection_string": "", "host": "", "port": 0, "user": "", "password": "",
             "database": "", "include_tables": ["fct_*", "dim_*"],
             "exclude_tables": ["temp_*"], "is_active": True},
        ]
        save_db_connections_sqlite()

        state._db_connections = []
        load_db_connections_sqlite()
        loaded = state._db_connections[0]
        assert loaded["include_tables"] == ["fct_*", "dim_*"]
        assert loaded["exclude_tables"] == ["temp_*"]
        assert loaded["is_active"] is True

    def test_delete_all(self, sqlite_db):
        from app import state
        state._db_connections = [
            {"id": "x", "name": "X", "type": "duckdb", "path": "/x",
             "connection_string": "", "host": "", "port": 0, "user": "", "password": "",
             "database": "", "include_tables": None, "exclude_tables": None, "is_active": False},
        ]
        save_db_connections_sqlite()

        state._db_connections = []
        save_db_connections_sqlite()
        load_db_connections_sqlite()
        assert state._db_connections == []


class TestConfigMigration:
    def test_migrate_from_old_config(self, sqlite_db):
        """Migrate old key-value config to new schema."""
        from app import state
        # Simulate old config table
        state._sqlite.execute("CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT)")
        state._sqlite.execute("INSERT INTO config VALUES ('llm_provider', 'deepseek')")
        state._sqlite.execute("INSERT INTO config VALUES ('llm_model', 'deepseek-v4-flash')")
        state._sqlite.execute("INSERT INTO config VALUES ('llm_api_key', 'sk-old')")
        state._sqlite.execute("INSERT INTO config VALUES ('llm_api_base', 'https://api.deepseek.com')")
        state._sqlite.commit()

        # This should trigger migration
        load_config_sqlite()

        # Old table should be gone
        old_exists = state._sqlite.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='config'"
        ).fetchone()
        assert old_exists is None

        # Data should be in new table
        row = state._sqlite.execute(
            "SELECT provider, model FROM llm_providers WHERE is_active=1"
        ).fetchone()
        assert row is not None
        assert row[0] == "deepseek"
        assert row[1] == "deepseek-v4-flash"

    def test_migrate_idempotent(self, sqlite_db):
        """Running migration twice should not duplicate data."""
        from app import state
        state._sqlite.execute("CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT)")
        state._sqlite.execute("INSERT INTO config VALUES ('llm_provider', 'openai')")
        state._sqlite.commit()

        load_config_sqlite()  # first migration
        load_config_sqlite()  # second

        rows = state._sqlite.execute(
            "SELECT count(*) FROM llm_providers WHERE is_active=1"
        ).fetchone()
        assert rows[0] == 1  # not duplicated
