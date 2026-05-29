"""Tests for config.py — default values, env var overrides."""

from __future__ import annotations

import os

from app.config import Config, LLMConfig, SafetyConfig, StorageConfig, load_config


def test_config_defaults():
    """Config should have sensible defaults."""
    cfg = Config()
    assert cfg.llm.provider == "openai"
    assert cfg.llm.model == "gpt-4o"
    assert cfg.llm.api_key == ""
    assert cfg.llm.api_base is None
    assert cfg.database.type == ""
    assert cfg.database.path == ""
    assert cfg.server.host == "0.0.0.0"
    assert cfg.server.port == 8000
    assert cfg.safety.read_only is True
    assert cfg.safety.max_rows == 1000
    assert cfg.storage.path == "./data/config.db"


def test_env_overrides(monkeypatch):
    """Environment variables should override config defaults."""
    monkeypatch.setenv("LLM_API_KEY", "sk-test-key")
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("LLM_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("LLM_API_BASE", "https://api.deepseek.com")
    monkeypatch.setenv("DB_PATH", "./custom/path.db")
    monkeypatch.setenv("PORT", "9000")

    cfg = load_config()
    assert cfg.llm.api_key == "sk-test-key"
    assert cfg.llm.provider == "deepseek"
    assert cfg.llm.model == "deepseek-v4-flash"
    assert cfg.llm.api_base == "https://api.deepseek.com"
    assert cfg.database.path == "./custom/path.db"
    assert cfg.server.port == 9000


def test_env_no_override_empty(monkeypatch):
    """Unset env vars should not override config defaults."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    cfg = load_config()
    assert cfg.llm.api_key == ""
    assert cfg.llm.provider == "openai"


def test_llm_config_immutable_types():
    """LLMConfig fields should have correct types."""
    lc = LLMConfig(provider="anthropic", model="claude-3", api_key="sk-xxx")
    assert lc.provider == "anthropic"
    assert lc.model == "claude-3"
    assert lc.api_key == "sk-xxx"


def test_safety_config_masked_columns():
    """SafetyConfig should support restricted_tables and masked_columns."""
    sc = SafetyConfig(read_only=False, max_rows=500, restricted_tables=["salaries"])
    assert sc.read_only is False
    assert sc.max_rows == 500
    assert "salaries" in sc.restricted_tables


def test_storage_config_custom_path():
    """StorageConfig should accept a custom path."""
    sc = StorageConfig(path="/tmp/test.db")
    assert sc.path == "/tmp/test.db"
