"""Tests for Schema Retriever — RAG retrieval pipeline."""

from __future__ import annotations

import pytest

from app.router.schema_retriever import _build_table_search_text, init_rag


class TestBuildTableSearchText:
    def test_name_only(self):
        text = _build_table_search_text("users")
        assert text == "users"

    def test_name_with_description(self):
        text = _build_table_search_text("users", description="用户表")
        assert "users" in text
        assert "用户表" in text

    def test_name_with_bilingual_descriptions(self):
        text = _build_table_search_text("users", description="用户表", description_en="users table")
        assert "users" in text
        assert "用户表" in text
        assert "users table" in text


class TestInitRAG:
    def test_init_sets_globals(self):
        init_rag("mock_embedding", "mock_vector_store")
        from app.router import schema_retriever as sr
        assert sr._embedding_service == "mock_embedding"
        assert sr._vector_store == "mock_vector_store"
        init_rag(None, None)


class TestRebuildEmbeddings:
    @pytest.mark.asyncio
    async def test_skip_when_not_initialized(self):
        init_rag(None, None)
        from app.router.schema_retriever import rebuild_embeddings
        result = await rebuild_embeddings("test-db")
        assert result is None

    @pytest.mark.asyncio
    async def test_rebuild_with_mock(self):
        class MockEmbeddingService:
            async def embed_batch(self, texts):
                return [[0.1, 0.2]] * len(texts)

        class MockVectorStore:
            def __init__(self):
                self.items = []

            def upsert_batch_tables(self, database_id, items):
                self.items = items

        mock_emb = MockEmbeddingService()
        mock_vs = MockVectorStore()
        init_rag(mock_emb, mock_vs)

        from app.router.schema_retriever import rebuild_embeddings
        from app import state
        from app.config import Config

        state.config = Config()
        await rebuild_embeddings("test-db")
        init_rag(None, None)


class TestRetrieveSchema:
    @pytest.mark.asyncio
    async def test_fallback_when_not_initialized(self):
        init_rag(None, None)
        from app.router.schema_retriever import retrieve_schema
        result = await retrieve_schema("test question", "db1", [])
        assert result["tier_hit"] == "fallback"
        assert "prompt" in result

    @pytest.mark.asyncio
    async def test_fallback_when_rag_disabled(self):
        class MockEmb:
            async def embed(self, text): return [0.1, 0.2]

        class MockVS:
            def search_tables(self, q, db_id, top_k=5, min_score=0.3): return []

        init_rag(MockEmb(), MockVS())
        from app import state
        from app.config import Config, RAGConfig
        state.config = Config()
        state.config.rag = RAGConfig(enabled=False)

        from app.router.schema_retriever import retrieve_schema
        result = await retrieve_schema("test", "db1", [])
        assert result["tier_hit"] == "fallback"
        init_rag(None, None)
