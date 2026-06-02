"""Tests for ChromaDB-backed VectorStore."""

from __future__ import annotations

import tempfile

import pytest

from app.persistence.vector_store import VectorStore


@pytest.fixture
def store():
    vs = VectorStore(persist_dir=tempfile.mkdtemp())
    yield vs
    vs.close()


class TestVectorStore:
    def test_upsert_and_search_table(self, store: VectorStore):
        store.upsert_table("db1", "t1", "users", "users table with names", [0.1, 0.2, 0.3])
        store.upsert_table("db1", "t2", "orders", "orders table with amounts", [0.9, 0.8, 0.7])
        results = store.search_tables([0.85, 0.8, 0.75], "db1", top_k=2)
        assert len(results) == 2
        assert results[0]["table_name"] == "orders"

    def test_search_filters_by_database_id(self, store: VectorStore):
        store.upsert_table("db1", "t1", "users", "users", [0.1, 0.2, 0.3])
        store.upsert_table("db2", "t2", "products", "products", [0.9, 0.8, 0.7])
        results = store.search_tables([0.9, 0.8, 0.7], "db2", top_k=5)
        assert len(results) == 1
        assert results[0]["table_name"] == "products"

    def test_search_returns_empty_for_unknown_database(self, store: VectorStore):
        results = store.search_tables([0.1, 0.2], "nonexistent", top_k=5)
        assert results == []

    def test_min_score_filters_low_similarity(self, store: VectorStore):
        store.upsert_table("db1", "t1", "users", "users info", [1.0, 0.0, 0.0])
        store.upsert_table("db1", "t2", "products", "products catalog", [0.0, 1.0, 0.0])
        results = store.search_tables([1.0, 0.0, 0.0], "db1", top_k=5, min_score=0.9)
        assert len(results) == 1
        assert results[0]["table_name"] == "users"

    def test_batch_upsert(self, store: VectorStore):
        items = [
            ("t1", "users", "users table", [0.1, 0.2, 0.3]),
            ("t2", "orders", "orders table", [0.4, 0.5, 0.6]),
            ("t3", "products", "products table", [0.7, 0.8, 0.9]),
        ]
        store.upsert_batch_tables("db1", items)
        results = store.search_tables([0.7, 0.8, 0.9], "db1", top_k=5)
        assert len(results) == 3

    def test_delete_database(self, store: VectorStore):
        store.upsert_table("db1", "t1", "users", "users", [0.1, 0.2, 0.3])
        store.upsert_table("db1", "t2", "orders", "orders", [0.4, 0.5, 0.6])
        store.upsert_table("db2", "t3", "products", "products", [0.7, 0.8, 0.9])
        store.delete_database("db1")
        results_db1 = store.search_tables([0.1, 0.2, 0.3], "db1", top_k=5)
        results_db2 = store.search_tables([0.7, 0.8, 0.9], "db2", top_k=5)
        assert results_db1 == []
        assert len(results_db2) == 1
