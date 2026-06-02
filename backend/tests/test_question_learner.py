"""Tests for question learner — self-learning system."""

from __future__ import annotations

import pytest

from app.router.question_learner import init_learner


class TestInitLearner:
    def test_init_sets_globals(self):
        init_learner("mock_emb", "mock_vs")
        from app.router import question_learner as ql
        assert ql._embedding_service == "mock_emb"
        assert ql._vector_store == "mock_vs"
        init_learner(None, None)


class TestLearn:
    @pytest.mark.asyncio
    async def test_skipped_when_not_initialized(self):
        init_learner(None, None)
        from app.router.question_learner import learn
        result = await learn("test question", "SELECT 1", ["users"], "db1", success=True, self_learn_enabled=True)
        assert result is None

    @pytest.mark.asyncio
    async def test_skipped_when_self_learn_disabled(self):
        class MockEmb:
            pass

        init_learner(MockEmb(), MockEmb())
        from app.router.question_learner import learn
        result = await learn("test question", "SELECT 1", ["users"], "db1", success=True, self_learn_enabled=False)
        assert result is None

    @pytest.mark.asyncio
    async def test_skipped_when_sql_failed(self):
        init_learner("mock", "mock")
        from app.router.question_learner import learn
        result = await learn("test question", "SELECT 1", ["users"], "db1", success=False, self_learn_enabled=True)
        assert result is None

    @pytest.mark.asyncio
    async def test_skipped_when_no_sql(self):
        init_learner("mock", "mock")
        from app.router.question_learner import learn
        result = await learn("test question", "", ["users"], "db1", success=True, self_learn_enabled=True)
        assert result is None

    @pytest.mark.asyncio
    async def test_skipped_when_no_question(self):
        init_learner("mock", "mock")
        from app.router.question_learner import learn
        result = await learn("", "SELECT 1", ["users"], "db1", success=True, self_learn_enabled=True)
        assert result is None
