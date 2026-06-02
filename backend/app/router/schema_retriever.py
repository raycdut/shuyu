"""Schema Router — Embed → Vector Search → Format.

Replaces build_schema_prompt() when RAG is enabled.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("shuyu.rag")

_embedding_service = None
_vector_store = None


def init_rag(embedding_service, vector_store):
    """Initialize RAG global instances at startup."""
    global _embedding_service, _vector_store
    _embedding_service = embedding_service
    _vector_store = vector_store


def _build_table_search_text(table_name: str, description: str = "",
                             description_en: str = "") -> str:
    """Build the text to embed for a table: name + descriptions."""
    parts = [table_name]
    if description:
        parts.append(description)
    if description_en:
        parts.append(description_en)
    return " ".join(parts)


async def rebuild_embeddings(database_id: str):
    """Rebuild all table embeddings for a database from persisted schema."""
    if not all([_embedding_service, _vector_store]):
        logger.warning("RAG not initialized, skipping rebuild")
        return
    from ..persistence.schema import load_full_schema
    tables = load_full_schema(database_id)
    if not tables:
        logger.info(f"No tables found for database {database_id}, nothing to rebuild")
        return
    texts = [_build_table_search_text(t["table_name"], t.get("description", ""),
                                      t.get("description_en", "")) for t in tables]
    embeddings = await _embedding_service.embed_batch(texts)
    items = []
    for t, text, emb in zip(tables, texts, embeddings):
        items.append((t["id"], t["table_name"], text, emb))
    _vector_store.upsert_batch_tables(database_id, items)
    logger.info(f"Rebuilt {len(items)} table embeddings for database {database_id}")


async def retrieve_schema(
    question: str,
    database_id: str,
    tables: list,
    top_k: Optional[int] = None,
    min_score: Optional[float] = None,
) -> dict:
    """Retrieve relevant schema and return formatted prompt.

    Returns dict with keys:
      - prompt: str, the formatted schema prompt
      - tier_hit: str, "table" when RAG matched, "fallback" otherwise
      - match_score: float, best match score
      - table_count: int, number of relevant tables found

    Falls back to full build_schema_prompt() if RAG is not initialized
    or no relevant tables found.
    """
    from ..config import PROJECT_ROOT
    from ..db.schema import build_schema_prompt

    fallback = lambda: {
        "prompt": build_schema_prompt(tables, database_id),
        "tier_hit": "fallback",
        "match_score": 0.0,
        "table_count": len(tables),
    }

    if not all([_embedding_service, _vector_store]):
        logger.info("RAG not initialized, falling back to full schema")
        return fallback()

    from .. import state
    cfg = state.config.rag if hasattr(state.config, 'rag') else None
    if not cfg or not cfg.enabled:
        return fallback()

    top_k = top_k or cfg.top_k
    min_score = min_score or cfg.min_score

    try:
        q_vector = await _embedding_service.embed(question)
        results = _vector_store.search_tables(
            q_vector, database_id, top_k=top_k, min_score=min_score
        )
        if not results:
            logger.info(f"No relevant tables found (min_score={min_score}), falling back")
            return fallback()

        matched_ids = {r["table_id"] for r in results}
        from ..persistence.schema import load_full_schema
        full_tables = load_full_schema(database_id)
        relevant = [t for t in full_tables if t["id"] in matched_ids]
        if not relevant:
            return fallback()

        matched_scores = {r["table_id"]: r["score"] for r in results}
        relevant.sort(key=lambda t: matched_scores.get(t["id"], 0), reverse=True)

        formatted = build_schema_prompt(relevant, database_id)
        header = (f"<rag note=\"已根据问题语义检索到 {len(relevant)} 张相关表，其余表已过滤\">\n")
        best_score = results[0]["score"] if results else 0.0
        return {
            "prompt": header + formatted,
            "tier_hit": "table",
            "match_score": best_score,
            "table_count": len(relevant),
        }
    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}, falling back to full schema")
        return fallback()
