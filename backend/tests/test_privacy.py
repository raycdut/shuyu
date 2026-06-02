"""Tests for privacy compliance — RAG data deletion."""

from __future__ import annotations

import tempfile

import pytest

from app.persistence.vector_store import VectorStore


@pytest.fixture
def store():
    vs = VectorStore(persist_dir=tempfile.mkdtemp())
    yield vs
    vs.close()


class TestPrivacy:
    def test_delete_hypotheses_by_database(self, store: VectorStore):
        store.store_hypothesis("h1", "db1", "question 1", '["t1"]', "SELECT 1", [0.1, 0.2], 1000.0)
        store.store_hypothesis("h2", "db1", "question 2", '["t2"]', "SELECT 1", [0.3, 0.4], 1000.0)
        store.store_hypothesis("h3", "db2", "question 3", '["t3"]', "SELECT 1", [0.5, 0.6], 1000.0)
        store.delete_hypotheses("db1")
        results_db1 = store.search_hypotheses([0.1, 0.2], "db1", top_k=5, min_score=0.0)
        results_db2 = store.search_hypotheses([0.5, 0.6], "db2", top_k=5, min_score=0.0)
        assert results_db1 == []
        assert len(results_db2) == 1

    def test_delete_hypotheses_does_not_affect_tables(self, store: VectorStore):
        store.upsert_table("db1", "t1", "users", "users table", [0.1, 0.2])
        store.store_hypothesis("h1", "db1", "test question", '["t1"]', "SELECT 1", [0.1, 0.2], 1000.0)
        store.delete_hypotheses("db1")
        tables = store.search_tables([0.1, 0.2], "db1", top_k=5)
        assert len(tables) == 1

    def test_delete_hypotheses_empty_database(self, store: VectorStore):
        store.delete_hypotheses("nonexistent")
        results = store.search_hypotheses([0.1, 0.2], "nonexistent", top_k=5, min_score=0.0)
        assert results == []
