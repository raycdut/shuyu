import pytest
import json
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
    from app.auth.service import init_auth_config
    init_auth_config()
    import app.state as state
    state.config.llm.api_key = "test-key"
    state.config.llm.api_base = "https://test.api.com"
    state.config.llm.timeout = 60
    state.config.llm.model = "gpt-4o"
    state.config.llm.provider = "openai"
    yield


class TestSystemConfig:
    def test_get_default_config(self):
        config = get_system_config()
        assert "llm" in config
        assert "safety" in config
        assert "advanced" in config
        assert "storage" in config
        assert len(config["llm"]["models"]) > 0

    def test_update_system_config(self):
        update_system_config({"safety": {"max_rows": 5000}}, updated_by="admin")
        config = get_system_config()
        assert config["safety"]["max_rows"] == 5000

    def test_partial_update_merges(self):
        models = get_system_config()["llm"]["models"]
        models[0]["model"] = "gpt-4o-mini"
        update_system_config({"llm": {"models": models}}, updated_by="admin")
        config = get_system_config()
        assert config["llm"]["models"][0]["model"] == "gpt-4o-mini"
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
        models = get_system_config()["llm"]["models"]
        deepseek_model = next((m for m in models if "deepseek" in m["model"]), models[0])
        update_system_config({"advanced": {"allow_user_llm_config": True}})
        update_user_config("user-1", {"llm": {"default_model_id": deepseek_model["id"]}})
        merged = get_merged_config("user-1")
        assert merged["llm"]["model"] == deepseek_model["model"]


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
