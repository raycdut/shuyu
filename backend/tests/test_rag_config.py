import pytest
from app.admin_config.service import (
    DEFAULT_SYSTEM_CONFIG,
    get_system_config,
    update_system_config,
    get_system_config_masked,
)
from app.config import RAGConfig, Config


class TestRAGConfigModel:
    def test_default_values(self):
        cfg = RAGConfig()
        assert cfg.enabled is False
        assert cfg.provider == "openai"
        assert cfg.model == "text-embedding-3-small"
        assert cfg.api_key == ""
        assert cfg.api_base == ""
        assert cfg.top_k == 5
        assert cfg.min_score == 0.3
        assert cfg.self_learn is False

    def test_in_config_object(self):
        cfg = Config()
        assert isinstance(cfg.rag, RAGConfig)
        assert cfg.rag.enabled is False

    def test_custom_values(self):
        cfg = RAGConfig(enabled=True, provider="siliconflow", model="BAAI/bge-m3", top_k=10, min_score=0.5)
        assert cfg.enabled is True
        assert cfg.provider == "siliconflow"
        assert cfg.model == "BAAI/bge-m3"
        assert cfg.top_k == 10
        assert cfg.min_score == 0.5


class TestRAGInSystemConfig:
    def test_default_system_config_contains_rag(self):
        assert "rag" in DEFAULT_SYSTEM_CONFIG
        rag = DEFAULT_SYSTEM_CONFIG["rag"]
        assert rag["enabled"] is False
        assert rag["provider"] == "openai"
        assert rag["model"] == "text-embedding-3-small"
        assert rag["top_k"] == 5
        assert rag["min_score"] == 0.3
        assert rag["self_learn"] is False

    def test_get_system_config_returns_rag_defaults(self):
        config = get_system_config()
        assert "rag" in config
        rag = config["rag"]
        assert rag["enabled"] is False
        assert rag["top_k"] == 5

    def test_update_rag_enabled(self):
        result = update_system_config({"rag": {"enabled": True}}, updated_by="admin")
        assert result["rag"]["enabled"] is True
        config = get_system_config()
        assert config["rag"]["enabled"] is True

    def test_update_rag_top_k(self):
        update_system_config({"rag": {"top_k": 8, "min_score": 0.4}}, updated_by="admin")
        config = get_system_config()
        assert config["rag"]["top_k"] == 8
        assert config["rag"]["min_score"] == 0.4

    def test_update_rag_does_not_affect_other_sections(self):
        update_system_config({"rag": {"enabled": True}}, updated_by="admin")
        config = get_system_config()
        assert config["safety"]["read_only"] is True
        assert len(config["llm"]["models"]) > 0

    def test_masked_config_hides_rag_api_key(self):
        update_system_config({"rag": {"api_key": "sk-test-key-12345"}}, updated_by="admin")
        masked = get_system_config_masked()
        key = masked["rag"]["api_key"]
        assert "••••" in key
        assert key.startswith("sk-t") and "2345" in key

    def test_rag_update_logs_changelog(self):
        from app.admin_config.service import get_config_changelog
        update_system_config({"rag": {"enabled": True}}, updated_by="admin")
        logs = get_config_changelog("system")
        assert any("rag" in log["summary"].lower() for log in logs)


class TestRAGConfigApiBaseWhitelist:
    def test_accepts_public_api_base(self):
        result = update_system_config({"rag": {"api_base": "https://api.openai.com/v1"}}, updated_by="admin")
        assert result["rag"]["api_base"] == "https://api.openai.com/v1"

    def test_accepts_siliconflow_api_base(self):
        result = update_system_config({"rag": {"api_base": "https://api.siliconflow.cn/v1"}}, updated_by="admin")
        assert result["rag"]["api_base"] == "https://api.siliconflow.cn/v1"
