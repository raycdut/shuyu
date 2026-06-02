# Shuyu RAG — Phase 1 Implementation Plan

> Exact code changes for the MVP RAG integration.
> Branch: `feature/enable-rag`

---

## File Changes Overview

```
NEW  backend/app/persistence/vector_store.py   (80 lines)
NEW  backend/app/embedding/service.py           (60 lines)
NEW  backend/app/router/schema_retriever.py     (100 lines)
MOD  backend/app/config.py                      (+15 lines)
MOD  backend/app/client.py                      (+20 lines)
MOD  backend/app/routes/chat.py                 (~10 lines changed)
MOD  backend/app/routes/schema.py               (+10 lines)
MOD  backend/app/state.py                       (+1 line)
```

---

## Step-by-step

### Step 1: `embedding/service.py` — Embedding abstraction

```python
"""Embedding service abstraction — supports pluggable providers."""

import logging
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

logger = logging.getLogger("shuyu.embedding")

class EmbeddingService(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...

class OpenAIEmbeddingService(EmbeddingService):
    """Uses OpenAI text-embedding-3-small via the chat-derived API key."""
    
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.model = model
        self._client = None
    
    async def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client
    
    async def embed(self, text: str) -> list[float]:
        client = await self._get_client()
        resp = await client.embeddings.create(model=self.model, input=text)
        return resp.data[0].embedding
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        client = await self._get_client()
        resp = await client.embeddings.create(model=self.model, input=texts)
        # Maintain input order
        ordered = sorted(resp.data, key=lambda x: x.index)
        return [d.embedding for d in ordered]

class SiliconFlowEmbeddingService(EmbeddingService):
    """SiliconFlow API — China-friendly, BAAI/bge-m3 or similar."""
    
    def __init__(self, api_key: str, model: str = "BAAI/bge-m3"):
        self.api_key = api_key
        self.model = model
    
    async def _embed(self, input_data):
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.siliconflow.cn/v1"
        )
        resp = await client.embeddings.create(model=self.model, input=input_data)
        return resp
    
    async def embed(self, text: str) -> list[float]:
        resp = await self._embed(text)
        return resp.data[0].embedding
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        resp = await self._embed(texts)
        ordered = sorted(resp.data, key=lambda x: x.index)
        return [d.embedding for d in ordered]

# Factory
def create_embedding_service(provider: str, api_key: str, model: str) -> EmbeddingService:
    if provider == "openai":
        return OpenAIEmbeddingService(api_key, model)
    elif provider == "siliconflow":
        return SiliconFlowEmbeddingService(api_key, model)
    else:
        raise ValueError(f"Unsupported embedding provider: {provider}")
```

### Step 2: `persistence/vector_store.py` — SQLite-backed vector index

```python
"""SQLite-backed vector store with numpy cosine similarity.

Stores table/column embeddings alongside their metadata.
No external vector DB needed for MVP — works in-process with the
existing ConfigDB SQLite connection.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("shuyu.vector")

# Embedding dimension for text-embedding-3-small
DEFAULT_DIM = 1536


class VectorStore:
    """Simple SQLite-backed vector store with numpy cosine similarity."""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from ..config import PROJECT_ROOT
            db_path = str(PROJECT_ROOT / "backend" / "data" / "vectors.db")
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
    
    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS table_embeddings (
                    database_id TEXT NOT NULL,
                    table_id    TEXT NOT NULL,
                    table_name  TEXT NOT NULL,
                    text        TEXT NOT NULL,       -- indexed text (name + desc)
                    embedding   BLOB NOT NULL,       -- numpy float32 bytes
                    dim         INTEGER NOT NULL,
                    PRIMARY KEY (database_id, table_id)
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS column_embeddings (
                    database_id TEXT NOT NULL,
                    table_id    TEXT NOT NULL,
                    column_id   TEXT NOT NULL,
                    column_name TEXT NOT NULL,
                    text        TEXT NOT NULL,
                    embedding   BLOB NOT NULL,
                    dim         INTEGER NOT NULL,
                    PRIMARY KEY (database_id, column_id)
                )
            """)
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn
    
    def upsert_table(self, database_id: str, table_id: str, table_name: str,
                     text: str, embedding: list[float]):
        conn = self._get_conn()
        blob = np.array(embedding, dtype=np.float32).tobytes()
        conn.execute(
            "INSERT OR REPLACE INTO table_embeddings VALUES (?,?,?,?,?,?)",
            (database_id, table_id, table_name, text, blob, len(embedding))
        )
        conn.commit()
    
    def upsert_batch_tables(self, database_id: str, 
                            items: list[tuple[str, str, str, list[float]]]):
        """Batch upsert: [(table_id, table_name, text, embedding), ...]"""
        conn = self._get_conn()
        rows = []
        for table_id, table_name, text, emb in items:
            blob = np.array(emb, dtype=np.float32).tobytes()
            rows.append((database_id, table_id, table_name, text, blob, len(emb)))
        conn.executemany(
            "INSERT OR REPLACE INTO table_embeddings VALUES (?,?,?,?,?,?)",
            rows
        )
        conn.commit()
    
    def search_tables(self, query_embedding: list[float], database_id: str,
                      top_k: int = 5, min_score: float = 0.3) -> list[dict]:
        """Search by cosine similarity. Returns [{table_id, table_name, text, score}]"""
        conn = self._get_conn()
        q = np.array(query_embedding, dtype=np.float32)
        q_norm = q / (np.linalg.norm(q) + 1e-10)
        
        rows = conn.execute(
            "SELECT table_id, table_name, text, embedding, dim FROM table_embeddings WHERE database_id=?",
            (database_id,)
        ).fetchall()
        
        results = []
        for table_id, table_name, text, blob, dim in rows:
            stored = np.frombuffer(blob, dtype=np.float32)
            s_norm = stored / (np.linalg.norm(stored) + 1e-10)
            score = float(np.dot(q_norm, s_norm))
            if score >= min_score:
                results.append({
                    "table_id": table_id,
                    "table_name": table_name,
                    "text": text,
                    "score": round(score, 4),
                })
        
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]
    
    def delete_database(self, database_id: str):
        conn = self._get_conn()
        conn.execute("DELETE FROM table_embeddings WHERE database_id=?", (database_id,))
        conn.execute("DELETE FROM column_embeddings WHERE database_id=?", (database_id,))
        conn.commit()
    
    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
```

### Step 3: `router/schema_retriever.py` — Retrieval pipeline

```python
"""Schema Router — Embed → Vector Search → Format.

Replaces build_schema_prompt() when RAG is enabled.
"""

import logging
from typing import Optional

from ..persistence.schema import load_full_schema
from ..db.schema import build_schema_prompt

logger = logging.getLogger("shuyu.rag")

# Global, initialized at startup
_embedding_service = None  # EmbeddingService
_vector_store = None       # VectorStore
_rag_config = None         # RAGConfig


def init_rag(embedding_service, vector_store, rag_config):
    global _embedding_service, _vector_store, _rag_config
    _embedding_service = embedding_service
    _vector_store = vector_store
    _rag_config = rag_config


def _build_table_search_text(table: dict) -> str:
    """Build the text to embed for a table: name + descriptions."""
    parts = [table["table_name"]]
    if table.get("description"):
        parts.append(table["description"])
    if table.get("description_en"):
        parts.append(table["description_en"])
    return " ".join(parts)


async def rebuild_embeddings(database_id: str):
    """Rebuild all table embeddings for a database."""
    if not all([_embedding_service, _vector_store, _rag_config]):
        logger.warning("RAG not initialized, skipping rebuild")
        return
    
    tables = load_full_schema(database_id)
    if not tables:
        return
    
    texts = [_build_table_search_text(t) for t in tables]
    embeddings = await _embedding_service.embed_batch(texts)
    
    items = []
    for t, text, emb in zip(tables, texts, embeddings):
        items.append((t["id"], t["table_name"], text, emb))
    
    _vector_store.upsert_batch_tables(database_id, items)
    logger.info(f"Rebuilt {len(items)} table embeddings for database {database_id}")


async def retrieve_schema(
    question: str,
    database_id: str,
    tables: list,  # the connector.get_schema() result
    top_k: Optional[int] = None,
    min_score: Optional[float] = None,
) -> str:
    """Retrieve relevant schema and return formatted prompt.
    
    Falls back to full build_schema_prompt() if:
    - RAG is not initialized
    - No embeddings exist yet
    - Embedding service fails
    """
    if not all([_embedding_service, _vector_store, _rag_config]):
        logger.info("RAG not initialized, falling back to full schema")
        return build_schema_prompt(tables, database_id)
    
    cfg = _rag_config
    top_k = top_k or cfg.top_k
    min_score = min_score or cfg.min_score
    
    try:
        # 1. Embed question
        q_vector = await _embedding_service.embed(question)
        
        # 2. Search
        results = _vector_store.search_tables(
            q_vector, database_id, top_k=top_k, min_score=min_score
        )
        
        if not results:
            logger.info(f"No relevant tables found (min_score={min_score}), falling back to full schema")
            return build_schema_prompt(tables, database_id)
        
        # 3. Load full schema for matched tables
        matched_ids = {r["table_id"] for r in results}
        matched_scores = {r["table_id"]: r["score"] for r in results}
        
        filtered_tables = [
            t for t in tables
            if any(ct["id"] in matched_ids for ct in ([t] if not hasattr(t, 'id') else []))
        ]
        
        # Different connector types return different schema formats
        # DuckDB: Table namedtuple with .name/.columns
        # MySQL/PG: similar
        # Fall back to load_full_schema for the matched table IDs
        from ..persistence.schema import load_imported_columns
        
        full_tables = load_full_schema(database_id)
        relevant = [t for t in full_tables if t["id"] in matched_ids]
        
        # Sort by score descending
        relevant.sort(key=lambda t: matched_scores.get(t["id"], 0), reverse=True)
        
        if not relevant:
            return build_schema_prompt(tables, database_id)
        
        # Format using the existing build_schema_prompt logic
        # (reuse its text format since it's proven)
        formatted = build_schema_prompt(relevant, database_id)
        
        # Add RAG header so agent knows it's seeing filtered schema
        header = f"<rag note=\"已根据问题语义检索到 {len(relevant)} 张相关表，其余表已过滤\">\n"
        return header + formatted
        
    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}, falling back to full schema")
        return build_schema_prompt(tables, database_id)
```

### Step 4: `config.py` — Add RAGConfig

```python
class RAGConfig(BaseModel):
    enabled: bool = False
    provider: str = "openai"
    model: str = "text-embedding-3-small"
    top_k: int = 5
    min_score: float = 0.3

# In Config class:
rag: RAGConfig = RAGConfig()

# Env var overrides:
("rag", "enabled"): "RAG_ENABLED",
("rag", "provider"): "RAG_PROVIDER",
("rag", "model"): "RAG_MODEL",
("rag", "top_k"): "RAG_TOP_K",
```

### Step 5: `client.py` — Add embed()

```python
# Add alongside existing call_llm():

_embedding_service_instance = None


def get_embedding_service():
    """Get or create the embedding service based on current config."""
    global _embedding_service_instance
    if _embedding_service_instance is None:
        from .embedding.service import create_embedding_service
        _embedding_service_instance = create_embedding_service(
            provider=state.config.rag.provider,
            api_key=state.config.llm.api_key,
            model=state.config.rag.model,
        )
    return _embedding_service_instance
```

### Step 6: `routes/chat.py` — Injection point change

```python
# In the chat handler, replace:
#   schema_text = build_schema_prompt(tables, req.db_id)
# with:

if state.config.rag.enabled:
    from ..router.schema_retriever import retrieve_schema
    schema_text = await retrieve_schema(
        question=req.message,
        database_id=req.db_id,
        tables=tables,  # from connector.get_schema()
    )
else:
    from ..db.schema import build_schema_prompt
    schema_text = build_schema_prompt(tables, req.db_id)
```

### Step 7: `state.py` — Add RAG config reference

```python
# No change needed — RAGConfig is part of Config object already in state.config.rag
```

### Step 8: `routes/schema.py` — Auto-rebuild on import

```python
# After schema import succeeds (in the import handler):
if state.config.rag.enabled:
    from ..router.schema_retriever import rebuild_embeddings
    await rebuild_embeddings(db_id)
```

---

## Verification Checklist

| # | Check | Expected |
|---|-------|----------|
| 1 | RAG disabled (default) | Behaviour identical to current production |
| 2 | RAG enabled with no embeddings | Falls back to full schema gracefully |
| 3 | RAG enabled with embeddings | Top-K relevant tables injected |
| 4 | Schema re-imported | Embeddings rebuilt automatically |
| 5 | Embedding service unreachable | Falls back to full schema (no crash) |
| 6 | Multi-turn chat across RAG/non-RAG | Session works correctly |
| 7 | Both fast mode and quality mode | RAG applies to both |
| 8 | Toggle RAG mid-session | Rebuilds schema prompt on next query |

---

## Testing

```bash
# Unit tests
pytest tests/test_vector_store.py -v
pytest tests/test_schema_retriever.py -v
pytest tests/test_embedding_service.py -v

# Integration: chat with RAG
RAG_ENABLED=true pytest tests/test_chat_rag.py -v

# Regression: RAG disabled = no behaviour change
RAG_ENABLED=false pytest tests/test_chat.py -v
```
