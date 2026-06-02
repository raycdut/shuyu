"""Tests for Embedding service abstraction."""

from __future__ import annotations

import pytest

from app.embedding.service import (
    OpenAIEmbeddingService,
    SiliconFlowEmbeddingService,
    create_embedding_service,
)


class TestEmbeddingServiceFactory:
    def test_create_openai(self):
        svc = create_embedding_service("openai", "sk-test", "text-embedding-3-small")
        assert isinstance(svc, OpenAIEmbeddingService)
        assert svc.model == "text-embedding-3-small"

    def test_create_siliconflow(self):
        svc = create_embedding_service("siliconflow", "sk-test", "BAAI/bge-m3")
        assert isinstance(svc, SiliconFlowEmbeddingService)
        assert svc.model == "BAAI/bge-m3"

    def test_create_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unsupported embedding provider"):
            create_embedding_service("unknown", "sk-test", "model")


class TestOpenAIEmbeddingService:
    def test_init(self):
        svc = OpenAIEmbeddingService("sk-test", "text-embedding-3-small", api_base="https://api.openai.com/v1")
        assert svc.api_key == "sk-test"
        assert svc.model == "text-embedding-3-small"
        assert svc.api_base == "https://api.openai.com/v1"

    def test_init_default_api_base(self):
        svc = OpenAIEmbeddingService("sk-test", "text-embedding-ada-002")
        assert svc.api_base is None


class TestSiliconFlowEmbeddingService:
    def test_init(self):
        svc = SiliconFlowEmbeddingService("sk-test", "BAAI/bge-m3")
        assert svc.api_key == "sk-test"
        assert svc.model == "BAAI/bge-m3"
        assert svc.api_base == "https://api.siliconflow.cn/v1"

    def test_init_custom_api_base(self):
        svc = SiliconFlowEmbeddingService("sk-test", "BAAI/bge-m3", api_base="https://custom.example.com/v1")
        assert svc.api_base == "https://custom.example.com/v1"
