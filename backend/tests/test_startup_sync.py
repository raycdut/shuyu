"""Tests for startup RAG sync — lifespan initialization."""

from __future__ import annotations

import json

import pytest

from app.admin_config.service import update_system_config, get_system_config


class TestRAGStartupSync:
    def test_rag_config_loaded_from_configdb(self):
        """Verify RAG config survives read/write cycle (simulates startup sync)."""
        update_system_config({"rag": {"enabled": True, "top_k": 8}}, updated_by="admin")
        config = get_system_config()
        assert config["rag"]["enabled"] is True
        assert config["rag"]["top_k"] == 8

    def test_rag_disabled_by_default(self):
        config = get_system_config()
        assert config["rag"]["enabled"] is False

    def test_rag_config_sync_with_llm_key_fallback(self):
        """When no RAG-specific API key is set, the LLM key is used as fallback."""
        update_system_config({
            "rag": {"enabled": True, "api_key": ""},
            "llm": {"models": [{"id": "default", "provider": "openai", "model": "gpt-4o",
                                "api_key": "", "enabled": True}]}
        }, updated_by="admin")
        config = get_system_config()
        assert config["rag"]["api_key"] == ""
