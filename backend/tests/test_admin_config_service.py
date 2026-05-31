import pytest
import json
import sqlite3
from app.admin_config.service import (
    get_system_config,
    update_system_config,
    get_user_config,
    update_user_config,
    get_merged_config,
    get_user_available_options,
    get_config_changelog,
)


@pytest.fixture(autouse=True)
def setup_db():
    import app.state as state
    state._sqlite = sqlite3.connect(":memory:")
    state._sqlite.execute("PRAGMA journal_mode=WAL")
    state._sqlite.executescript("""
        CREATE TABLE IF NOT EXISTS system_config (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            config      TEXT NOT NULL DEFAULT '{}',
            updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_by  TEXT
        );
        CREATE TABLE IF NOT EXISTS user_configs (
            user_id     TEXT PRIMARY KEY,
            config      TEXT NOT NULL DEFAULT '{}',
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS config_changelog (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            config_type TEXT NOT NULL CHECK (config_type IN ('system', 'user')),
            user_id     TEXT,
            changed_by  TEXT NOT NULL,
            summary     TEXT NOT NULL,
            diff        TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    from app.auth.service import init_auth_config
    init_auth_config()
    from app.config import Config
    state.config = Config()
    state.config.llm.api_key = "test-key"
    state.config.llm.api_base = "https://test.api.com"
    state.config.llm.timeout = 60
    state.config.llm.model = "gpt-4o"
    state.config.llm.provider = "openai"
    yield
    state._sqlite.close()
    state._sqlite = None


class TestSystemConfig:
    def test_get_default_config(self):
        config = get_system_config()
        assert "llm" in config
        assert "safety" in config
        assert "advanced" in config
        assert "storage" in config
        assert len(config["llm"]["provider_pool"]) > 0

    def test_update_system_config(self):
        update_system_config({"safety": {"max_rows": 5000}}, updated_by="admin")
        config = get_system_config()
        assert config["safety"]["max_rows"] == 5000

    def test_partial_update_merges(self):
        update_system_config({"llm": {"default_model": "gpt-4o-mini"}}, updated_by="admin")
        config = get_system_config()
        assert config["llm"]["default_model"] == "gpt-4o-mini"
        assert config["safety"]["read_only"] is True

    def test_update_logs_changelog(self):
        update_system_config({"advanced": {"allow_user_llm_config": False}}, updated_by="admin")
        logs = get_config_changelog("system")
        assert len(logs) >= 1
        assert logs[0]["changed_by"] == "admin"


class TestUserConfig:
    def test_get_default_user_config(self):
        config = get_user_config("user-1")
        assert "llm" in config
        assert "preferences" in config
        assert config["preferences"]["language"] == "zh-CN"

    def test_update_user_config(self):
        result = update_user_config("user-1", {"preferences": {"language": "en"}})
        assert "merged" in result
        assert "overrides" in result
        assert result["merged"]["preferences"]["language"] == "en"

    def test_user_config_isolation(self):
        update_user_config("user-1", {"preferences": {"language": "en"}})
        update_user_config("user-2", {"preferences": {"language": "ja"}})
        assert get_user_config("user-1")["preferences"]["language"] == "en"
        assert get_user_config("user-2")["preferences"]["language"] == "ja"

    def test_user_llm_override(self):
        update_system_config({"advanced": {"allow_user_llm_config": True}})
        update_user_config("user-1", {"llm": {"provider": "deepseek", "model": "deepseek-v4-flash"}})
        merged = get_merged_config("user-1")
        assert merged["llm"]["provider"] == "deepseek"


class TestMergedConfig:
    def test_merged_without_user(self):
        merged = get_merged_config()
        assert "llm" in merged
        assert "safety" in merged
        assert merged["llm"]["provider"] in ("openai", "deepseek")

    def test_merged_respects_disabled_user_override(self):
        update_system_config({"advanced": {"allow_user_safety_override": False}})
        update_user_config("user-1", {"safety": {"read_only": False}})
        merged = get_merged_config("user-1")
        assert merged["safety"]["read_only"] is True

    def test_merged_respects_enabled_user_override(self):
        update_system_config({"advanced": {"allow_user_safety_override": True}})
        update_user_config("user-1", {"safety": {"read_only": False}})
        merged = get_merged_config("user-1")
        assert merged["safety"]["read_only"] is False

    def test_merged_enforces_max_rows_limit(self):
        update_system_config({"advanced": {"allow_user_safety_override": True}, "safety": {"max_rows": 100}})
        update_user_config("user-1", {"safety": {"max_rows": 9999}})
        merged = get_merged_config("user-1")
        assert merged["safety"]["max_rows"] <= 100


class TestAvailableOptions:
    def test_available_options(self):
        options = get_user_available_options("user-1")
        assert "llm" in options
        assert "safety" in options
        assert "preferences" in options
        assert len(options["llm"]["providers"]) > 0
        assert "language" in options["preferences"]
        assert options["preferences"]["language"]["options"] == ["zh-CN", "en", "ja"]

    def test_available_options_respects_enabled_providers(self):
        update_system_config({"llm": {"provider_pool": [
            {"provider": "openai", "label": "OpenAI", "models": ["gpt-4o"], "enabled": True},
            {"provider": "anthropic", "label": "Anthropic", "models": ["claude-3"], "enabled": False},
        ]}})
        options = get_user_available_options("user-1")
        assert len(options["llm"]["providers"]) == 1
        assert options["llm"]["providers"][0]["provider"] == "openai"


class TestChangelog:
    def test_changelog_ordered_by_time(self):
        update_system_config({"safety": {"max_rows": 100}}, updated_by="admin")
        import time; time.sleep(0.01)
        update_system_config({"advanced": {"allow_user_llm_config": False}}, updated_by="admin")
        logs = get_config_changelog("system")
        assert len(logs) >= 2
        assert "advanced" in logs[0]["summary"]
