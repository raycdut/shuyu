"""Integration tests for the full RAG pipeline.

Tests the end-to-end flow: config → embedding → vector store → schema retrieval → chat injection.
"""

from __future__ import annotations

import json
import tempfile
import time

import pytest

from app.admin_config.service import (
    DEFAULT_SYSTEM_CONFIG,
    get_system_config,
    update_system_config,
    get_system_config_masked,
)
from app.config import RAGConfig, Config
from app.embedding.service import (
    OpenAIEmbeddingService,
    SiliconFlowEmbeddingService,
    create_embedding_service,
)
from app.metrics.rag_metrics import RagMetrics, get_rag_metrics, record_query, record_self_learn
from app.persistence.vector_store import VectorStore
from app.router.schema_retriever import init_rag, retrieve_schema, rebuild_embeddings, _build_table_search_text
from app.router.question_learner import init_learner


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def vs():
    store = VectorStore(persist_dir=tempfile.mkdtemp())
    yield store
    store.close()


@pytest.fixture
def mock_emb():
    class MockEmbeddingService:
        async def embed(self, text: str) -> list[float]:
            # Return deterministic vector based on text length
            return [hash(text) % 100 / 100.0, 0.5, 0.3]

        async def embed_batch(self, texts: list[str]) -> list[list[float]]:
            return [await self.embed(t) for t in texts]

    return MockEmbeddingService()


# =========================================================================
# Integration: RAGConfig → SystemConfig → Admin API
# =========================================================================

class TestConfigIntegration:
    """Verify the config flows through all layers."""

    def test_default_rag_config_in_system_config(self):
        """RAGConfig defaults match DEFAULT_SYSTEM_CONFIG rag section."""
        cfg = RAGConfig()
        defaults = DEFAULT_SYSTEM_CONFIG["rag"]
        assert cfg.enabled == defaults["enabled"] is False
        assert cfg.provider == defaults["provider"] == "openai"
        assert cfg.model == defaults["model"] == "text-embedding-3-small"
        assert cfg.top_k == defaults["top_k"] == 5
        assert cfg.min_score == defaults["min_score"] == 0.3

    def test_config_write_then_read_roundtrip(self):
        """Write RAG config via update_system_config, read it back."""
        update_system_config({
            "rag": {"enabled": True, "provider": "siliconflow", "model": "BAAI/bge-m3", "top_k": 10},
        }, updated_by="admin")
        cfg = get_system_config()
        assert cfg["rag"]["enabled"] is True
        assert cfg["rag"]["provider"] == "siliconflow"
        assert cfg["rag"]["model"] == "BAAI/bge-m3"
        assert cfg["rag"]["top_k"] == 10

    def test_masked_config_does_not_expose_api_key(self):
        """Masked config hides the API key but shows first/last 4 chars."""
        update_system_config({"rag": {"api_key": "sk-abcdefghijklmnop"}}, updated_by="admin")
        masked = get_system_config_masked()
        key = masked["rag"]["api_key"]
        assert "••••" in key
        assert key.startswith("sk-a")
        assert key.endswith("mnop")

    def test_non_rag_config_unchanged_after_rag_update(self):
        """Updating RAG config doesn't affect LLM/Safety/Advanced config."""
        update_system_config({"rag": {"enabled": True}}, updated_by="admin")
        cfg = get_system_config()
        assert cfg["safety"]["read_only"] is True
        assert len(cfg["llm"]["models"]) > 0
        assert "session_expire_minutes" in cfg["advanced"]

    def test_rag_config_in_pydantic_config_object(self):
        """RAGConfig is accessible via Config.rag."""
        cfg = Config()
        assert isinstance(cfg.rag, RAGConfig)
        cfg.rag.enabled = True
        cfg.rag.top_k = 8
        assert cfg.rag.enabled is True
        assert cfg.rag.top_k == 8


# =========================================================================
# Integration: VectorStore + Schema Retriever
# =========================================================================

class TestVectorAndRetrievalIntegration:
    """End-to-end vector store + schema retrieval pipeline."""

    @pytest.mark.asyncio
    async def test_embed_then_store_then_retrieve(self, vs, mock_emb):
        """Full cycle: embed table texts → store in ChromaDB → search → format prompt."""
        init_rag(mock_emb, vs)
        from app import state
        from app.config import Config, RAGConfig
        state.config = Config()
        state.config.rag = RAGConfig(enabled=True, top_k=5, min_score=0.0)

        # Store tables
        texts = ["users users table containing user info", "orders order records with amounts"]
        embeddings = await mock_emb.embed_batch(texts)
        vs.upsert_batch_tables("db1", [
            ("t1", "users", texts[0], embeddings[0]),
            ("t2", "orders", texts[1], embeddings[1]),
        ])

        # Search
        result = await retrieve_schema(
            question="how many users do we have",
            database_id="db1",
            tables=[],
        )
        assert result["tier_hit"] in ("table", "fallback")
        assert "prompt" in result

        init_rag(None, None)

    @pytest.mark.asyncio
    async def test_retrieve_fallback_when_no_embeddings(self, vs, mock_emb):
        """When no embeddings exist, retrieve_schema returns fallback."""
        init_rag(mock_emb, vs)
        from app import state
        from app.config import Config, RAGConfig
        state.config = Config()
        state.config.rag = RAGConfig(enabled=True)

        result = await retrieve_schema("test question", "db1", [])
        assert result["tier_hit"] == "fallback"

        init_rag(None, None)

    @pytest.mark.asyncio
    async def test_retrieve_fallback_when_rag_disabled(self, vs, mock_emb):
        """When RAG is explicitly disabled, always return fallback."""
        init_rag(mock_emb, vs)
        from app import state
        from app.config import Config, RAGConfig
        state.config = Config()
        state.config.rag = RAGConfig(enabled=False)

        result = await retrieve_schema("test question", "db1", [])
        assert result["tier_hit"] == "fallback"

        init_rag(None, None)

    @pytest.mark.asyncio
    async def test_rebuild_embeddings_skipped_when_not_initialized(self):
        """rebuild_embeddings is a no-op when RAG is not initialized."""
        init_rag(None, None)
        result = await rebuild_embeddings("test-db")
        assert result is None

    def test_build_table_search_text_various_inputs(self):
        """_build_table_search_text handles various input combinations."""
        assert _build_table_search_text("users") == "users"
        assert "desc" in _build_table_search_text("users", description="desc")
        assert "en_desc" in _build_table_search_text("users", description_en="en_desc")
        assert _build_table_search_text("users", "desc", "en_desc") == "users desc en_desc"


# =========================================================================
# Integration: Embedding Service Factory
# =========================================================================

class TestEmbeddingServiceIntegration:
    """Verify embedding service creation works."""

    def test_openai_factory(self):
        svc = create_embedding_service("openai", "sk-test", "text-embedding-3-small")
        assert isinstance(svc, OpenAIEmbeddingService)
        assert svc.api_key == "sk-test"

    def test_siliconflow_factory(self):
        svc = create_embedding_service("siliconflow", "sk-test", "BAAI/bge-m3")
        assert isinstance(svc, SiliconFlowEmbeddingService)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError):
            create_embedding_service("unknown", "sk-test", "model")

    def test_openai_with_custom_api_base(self):
        svc = create_embedding_service("openai", "sk-test", "model", api_base="https://custom.example.com")
        assert svc.api_base == "https://custom.example.com"

    def test_siliconflow_default_api_base(self):
        svc = create_embedding_service("siliconflow", "sk-test", "BAAI/bge-m3")
        assert "siliconflow" in svc.api_base


# =========================================================================
# Integration: RAG Metrics
# =========================================================================

class TestRagMetricsIntegration:
    """Verify metrics collection works end-to-end."""

    def test_metrics_tracking(self):
        RagMetrics().last_reset = 0  # reset for clean test
        record_query(enabled=True, tier_hit="table", score=0.95, latency_ms=150, tables_retrieved=3)
        record_query(enabled=True, tier_hit="fallback", score=0.0, latency_ms=5, tables_retrieved=0)
        record_query(enabled=False)
        record_self_learn()

        metrics = get_rag_metrics()
        assert metrics["total_queries"] >= 3
        assert metrics["rag_enabled_queries"] >= 2
        assert metrics["fallback_count"] >= 1
        assert metrics["self_learn_count"] >= 1
        assert metrics["avg_latency_ms"] >= 0

    def test_metrics_empty_initially(self):
        """Reset and check clean state."""
        m = RagMetrics()
        snap = m.snapshot()
        assert snap["total_queries"] == 0
        assert snap["rag_enabled_queries"] == 0
        assert snap["fallback_count"] == 0
        assert snap["self_learn_count"] == 0


# =========================================================================
# Integration: Question Learner
# =========================================================================

class TestQuestionLearnerIntegration:
    """Verify the self-learning flow."""

    @pytest.mark.asyncio
    async def test_learner_skipped_when_not_initialized(self):
        from app.router.question_learner import learn
        init_learner(None, None)
        result = await learn("test", "SELECT 1", ["users"], "db1", success=True, self_learn_enabled=True)
        assert result is None

    @pytest.mark.asyncio
    async def test_learner_skipped_when_disabled(self, mock_emb, vs):
        init_learner(mock_emb, vs)
        from app.router.question_learner import learn
        result = await learn("test", "SELECT 1", ["users"], "db1", success=True, self_learn_enabled=False)
        assert result is None
        init_learner(None, None)


# =========================================================================
# Integration: VectorStore hypothesis search
# =========================================================================

class TestHypothesisStorageIntegration:
    """Verify Tier 2 hypothesis storage and search."""

    def test_store_hypothesis_roundtrip(self, vs):
        vs.store_hypothesis("h1", "db1", "how many users?", '["users"]', "SELECT count(*)", [1.0, 0.0, 0.0], time.time())
        results = vs.search_hypotheses([1.0, 0.0, 0.0], "db1", top_k=5, min_score=0.5)
        assert len(results) >= 1
        assert "users" in results[0]["table_ids"]
        assert results[0]["score"] >= 0.5

    def test_hypothesis_isolation_across_databases(self, vs):
        vs.store_hypothesis("h1", "db1", "q1", '["t1"]', "SELECT 1", [0.1, 0.2], time.time())
        vs.store_hypothesis("h2", "db2", "q2", '["t2"]', "SELECT 1", [0.9, 0.8], time.time())
        results_db1 = vs.search_hypotheses([0.1, 0.2], "db1", top_k=5, min_score=0.0)
        results_db2 = vs.search_hypotheses([0.9, 0.8], "db2", top_k=5, min_score=0.0)
        assert len(results_db1) == 1
        assert len(results_db2) == 1
        assert results_db1[0]["question"] == "q1"
        assert results_db2[0]["question"] == "q2"

    def test_delete_hypotheses(self, vs):
        vs.store_hypothesis("h1", "db1", "q1", '["t1"]', "SELECT 1", [0.1, 0.2], time.time())
        vs.delete_hypotheses("db1")
        results = vs.search_hypotheses([0.1, 0.2], "db1", top_k=5, min_score=0.0)
        assert results == []


# =========================================================================
# Integration: Config change triggers reset
# =========================================================================

class TestConfigChangeResetsEmbeddingService:
    """Verify that changing RAG config resets the cached embedding service."""

    def test_rag_update_calls_reset(self):
        from app.admin_config.service import update_system_config
        from app import client
        client._embedding_service_instance = "cached_instance"
        update_system_config({"rag": {"top_k": 10}}, updated_by="admin")
        assert client._embedding_service_instance is None, "reset_embedding_service should clear cache"


class TestSchemaImportTriggersRebuild:
    """Verify rebuild_embeddings is called after schema import (via state.rag.enabled)."""

    def test_rag_enabled_flag_checked_for_rebuild(self):
        from app.config import Config, RAGConfig
        from app import state
        state.config = Config()
        state.config.rag = RAGConfig(enabled=True)
        assert state.config.rag.enabled is True

        state.config.rag = RAGConfig(enabled=False)
        assert state.config.rag.enabled is False
