"""Post-query self-learning: generates hypothetical questions from real queries.

Fire-and-forget background task. Never blocks the user.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Optional

logger = logging.getLogger("shuyu.rag")

_embedding_service = None
_vector_store = None


def init_learner(embedding_service, vector_store):
    """Initialize learner global instances at startup."""
    global _embedding_service, _vector_store
    _embedding_service = embedding_service
    _vector_store = vector_store


async def learn(
    question: str,
    sql: str,
    tables: list[str],
    database_id: str,
    success: bool = True,
    self_learn_enabled: bool = False,
) -> None:
    """Generate hypothetical questions from a real user query and store them.

    Fire-and-forget: swallows all errors.
    """
    if not all([_embedding_service, _vector_store]):
        return
    if not self_learn_enabled or not success:
        return
    if not sql or not question:
        return

    try:
        from ..client import call_llm

        prompt = (
            f"用户问了以下问题，系统成功执行了对应的 SQL。\n\n"
            f"用户提问：{question}\n\n"
            f"SQL：{sql}\n\n"
            f"查询涉及的表：{', '.join(tables)}\n\n"
            f"生成 2-3 个不同的提问方式（不同的表达但同一个意思）。"
            f"直接返回 JSON 字符串数组。"
        )

        response = await call_llm(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            return
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]

        hypotheses = json.loads(content)
        if isinstance(hypotheses, dict):
            for key in ("questions", "hypotheses", "alternatives"):
                if key in hypotheses:
                    hypotheses = hypotheses[key]
                    break

        if not isinstance(hypotheses, list):
            return

        texts = [h.strip() for h in hypotheses if h.strip()]
        if not texts:
            return

        embeddings = await _embedding_service.embed_batch(texts)
        now = time.time()
        for text, embedding in zip(texts, embeddings):
            _vector_store.store_hypothesis(
                id=str(uuid.uuid4())[:8],
                database_id=database_id,
                question=text,
                table_ids=json.dumps(tables),
                source_query=sql,
                embedding=embedding,
                created_at=now,
            )

        logger.info(f"Stored {len(texts)} hypothetical questions from: {question[:50]}")
    except Exception as e:
        logger.warning(f"Self-learning skipped (non-fatal): {e}")
