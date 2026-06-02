# RAG-Enhanced Schema Retrieval for Shuyu

> Design document: adding semantic schema retrieval (RAG) to Shuyu's agent system.
> Branch: `feature/enable-rag`

---

## 1. Motivation

### Problem

Shuyu currently injects **the full database schema** (all table names, column names, types, descriptions) into the LLM prompt on every query. This works for small schemas (< 20 tables), but has known scaling issues:

| Issue | Impact |
|-------|--------|
| Token waste | Every query pays for irrelevant tables/columns |
| Distraction noise | LLM may pick wrong tables from a large pool |
| Schema size limit | Prompt budget capped by the model's context window |
| Multi-DB cross-query | Impossible to inject schemas from N databases simultaneously |

### Goal

Replace "inject all" with **semantic schema retrieval**: given a user question, retrieve only the top-K relevant tables and their columns before generating SQL.

---

## 2. Current Architecture (Baseline)

```
┌──────────────┐     ┌─────────────────────────────┐
│   User       │────▶│   POST /api/chat             │
│   (React UI) │     │   routes/chat.py             │
└──────────────┘     └───────────┬─────────────────┘
                                 │
                                 ▼
               ┌─────────────────────────────────┐
               │   Agent (SimpleAgent /           │
               │   AdvancedAgent)                 │
               │                                  │
               │   System Prompt includes:        │
               │   <database>                     │
               │     ALL tables + columns + desc  │
               │   </database>                    │
               └──────────┬──────────────────────┘
                          │
                          ▼
               ┌─────────────────────────────────┐
               │   SQL Tool (sql_tool.py)        │
               │   1. LLM generates SQL from      │
               │      full schema prompt          │
               │   2. Executes via DuckDB/MySQL/  │
               │      PostgreSQL connector        │
               └──────────┬──────────────────────┘
                          │
                          ▼
               ┌─────────────────────────────────┐
               │   Database (DuckDB/MySQL/PG)     │
               └─────────────────────────────────┘
```

### Key files in current flow

| File | Role |
|------|------|
| `routes/chat.py` | Entry point: loads schema, injects into agent messages |
| `db/schema.py` | `build_schema_prompt()` / `build_schema_light()` — format full schema |
| `persistence/schema.py` | `load_full_schema()` — loads ALL imported tables + columns from SQLite |
| `agent/simple_agent.py` | ReAct loop, schema in system prompt |
| `agent/advanced_agent.py` | Plan → Reflect → Execute → Report, schema in system prompt |
| `agent/tools/sql_tool.py` | `handle_query_database()` — SQL generation with full schema |
| `client.py` | `call_llm()` — unified LLM call |

### Schema injection point (`routes/chat.py`, lines 196-206)

```python
agent_messages.insert(0, {
    "role": "system",
    "content": f"<database name=\"{db_entry['name']}\">\n{inject_schema}\n</database>..."
})
```

---

## 3. Proposed RAG Architecture

### 3.1 High-level design

```
┌──────────────┐     ┌─────────────────────────────┐
│   User       │────▶│   POST /api/chat             │
│   (React UI) │     │   routes/chat.py             │
└──────────────┘     └───────────┬─────────────────┘
                                 │
                                 ▼
               ┌─────────────────────────────────┐
               │   Schema Router (NEW)            │
               │   router/schema_retriever.py     │
               │                                  │
               │   1. Embed user question         │
               │   2. Vector search → top-K tables│
               │   3. Return relevant schema only │
               └──────────┬──────────────────────┘
                          │
                          ▼
               ┌─────────────────────────────────┐
               │   Agent                          │
               │                                  │
               │   System Prompt includes:        │
               │   <database>                     │
               │     RELEVANT tables only (top-K) │
               │   </database>                    │
               └──────────┬──────────────────────┘
                          │
                          ▼
               ┌─────────────────────────────────┐
               │   SQL Tool (sql_tool.py)        │
               │   1. LLM generates SQL from      │
               │      relevant schema only        │
               │   2. Executes via connector      │
               └──────────┬──────────────────────┘
                          │
                          ▼
               ┌─────────────────────────────────┐
               │   Database (DuckDB/MySQL/PG)     │
               └─────────────────────────────────┘
                          ▲
                          │
               ┌─────────────────────────────────┐
               │   Vector Store (NEW)             │
               │   persistence/vector_store.py    │
               │                                  │
               │   Stores: table embeddings,      │
               │   column embeddings,             │
               │   description embeddings         │
               └─────────────────────────────────┘
```

### 3.2 New components

#### `persistence/vector_store.py` — Vector database abstraction

- Supports multiple backends via adapter pattern
- **Phase 1 backend**: In-process SQLite + numpy (self-calculated cosine similarity)
- **Phase 2 backend**: ChromaDB or FAISS (optional upgrade)
- Stores:
  - Table-level: `[table_name + description]` → embedding
  - Column-level: `[table_name.column_name + type + description]` → embedding
- CRUD: sync on schema import, incremental update

#### `router/schema_retriever.py` — On-query retrieval logic

```
Input:  user_question (str)
        active_db_id (str)
        top_k (int, default=5)

Steps:
1. Embed user question → q_vector
2. Search table-level index → top-K tables sorted by cosine similarity
3. For each matched table, load full column details from SQLite
4. Return {tables: [...table schemas...], embeddings: bool}

Output: formatted schema prompt (same shape as build_schema_prompt())
```

#### `embedding/` — Embedding service abstraction

```
EmbeddingService:
  - embed(text: str) -> list[float]
  - embed_batch(texts: list[str]) -> list[list[float]]
  - sync_on_import(db_id: str) — (re)build embeddings when schema is imported
```

Supports pluggable providers:
- **OpenAI** `text-embedding-3-small` (recommended default)
- **SiliconFlow** / BGE-M3 (China-friendly alternative)
- Local **sentence-transformers** (no API cost, higher latency)

### 3.3 Configuration additions (config.py)

```python
class RAGConfig(BaseModel):
    enabled: bool = False           # Master toggle
    backend: str = "sqlite"         # sqlite | chromadb | faiss
    provider: str = "openai"        # openai | siliconflow | local
    model: str = "text-embedding-3-small"
    top_k: int = 5                  # Tables to retrieve per query
    min_score: float = 0.3          # Minimum similarity threshold
    rebuild_on_import: bool = True  # Auto-rebuild embeddings on schema import
```

---

## 4. Data Flow Comparison

### Without RAG (current)

```
User: "上个月华东区销量排名"
                      │
                      ▼
 Load ALL schemas ────┤───────────────────────────
                      │  Table: orders (id, product_id, amount, region, date, ...)
                      │  Table: products (id, name, category, price, ...)
                      │  Table: customers (id, name, tier, location, ...)
                      │  Table: inventory (id, product_id, quantity, ...)
                      │  Table: suppliers (id, name, contact, ...)
                      │  ... 30+ more tables
                      ▼
 LLM reads all 30+ tables ───────▶ Generates SQL
                      │
                      ▼
 Problem: LLM might join "suppliers" because it has "region" column
```

### With RAG

```
User: "上个月华东区销量排名"
                      │
                      ▼
 Embed question ──────▶ Vector search
                      │
                      ▼
 Top-3 retrieved:     │  Table: orders (score 0.91 — matches "销量")
                      │    description: "订单表，记录每笔交易的金额、区域、时间"
                      │  Table: products (score 0.68 — matches "排名→产品")
                      │  Table: region (score 0.52)
                      │
                      ▼
 LLM receives only the 3 relevant tables ───────▶ Generates SQL
                      │
                      ▼
 Result: cleaner prompt, less noise, lower cost
```

---

## 5. Implementation Phases

### Phase 1 — MVP (Effort: ~1-2 days)

**Goal**: Functional RAG with OpenAI embedding + in-process vector search.

| Step | File | Change |
|------|------|--------|
| 1 | `persistence/vector_store.py` | Create SQLite-backed vector store with numpy cosine similarity |
| 2 | `client.py` | Add `embed()` method alongside `call_llm()` |
| 3 | `router/schema_retriever.py` | Create retrieval pipeline: embed → search → format |
| 4 | `routes/chat.py` | Replace `build_schema_prompt()` with `schema_retriever.retrieve()` |
| 5 | `config.py` | Add `RAGConfig` with `enabled` toggle |
| 6 | `routes/schema.py` | Webhook: auto-rebuild embeddings on schema import |

**Key decision**: Support OpenAI `text-embedding-3-small` as the default provider, with a config field to switch.

### Phase 2 — Schema Import Sync (Effort: ~1 day)

| Step | File | Change |
|------|------|--------|
| 1 | `persistence/vector_store.py` | Add `rebuild(db_id)` and `incremental_update()` methods |
| 2 | `agent/describe_schema_agent.py` | After descriptions are generated, trigger embedding rebuild |
| 3 | Database routes | Hook into `/api/database/import` to rebuild embeddings |

### Phase 3 — Multi-Provider & Optimization (Effort: ~2-3 days)

| Step | Change |
|------|--------|
| 1 | Add ChromaDB backend (optional, for larger schemas) |
| 2 | Add SiliconFlow / local BGE-M3 support |
| 3 | Embedding cache & batch processing |
| 4 | A/B comparison: RAG vs full-schema on query quality |
| 5 | Column-level retrieval (retrieve individual columns, not just tables) |

### Phase 4 — History-aware RAG (Future)

| Step | Change |
|------|--------|
| 1 | Index historical SQL queries as additional retrieval documents |
| 2 | Multi-turn context: carry over retrieved schema across chat turns |
| 3 | Feedback loop: user corrections → re-rank embedding weights |

---

## 6. Comparison Summary

| Dimension | Without RAG (current) | With RAG (proposed) |
|-----------|----------------------|---------------------|
| Schema injection | All tables, all columns | Top-K relevant tables only |
| Token cost per query | High (proportional to schema size) | Low (~O(top_k * columns_per_table)) |
| Query latency | Low (no embedding call) | + embedding latency (~100-300ms) |
| Accuracy (table selection) | LLM must infer from full list | Guaranteed by semantic match |
| Scalability | < 50 tables | 100+ tables |
| Cost | LLM token cost dominates | + cheap embedding cost |
| Dependencies | None | + Embedding API or local model |
| Configuration | Schema auto-loads | Toggle + top_k + provider |

### Token savings estimate

For a database with 30 tables × 15 columns = 450 column definitions:

| Scenario | Schema tokens (approx.) | Embedding cost | Total cost |
|----------|------------------------|----------------|------------|
| Without RAG | 3,000 - 5,000 | $0 | 3,000 - 5,000 tokens |
| With RAG (top-5) | 500 - 800 | ~$0.00004/query | 500 - 800 tokens + $0.00004 |

**Savings: 80-90% of schema tokens per query.**

For 1,000 queries/month:
- Without RAG: ~4M schema tokens × $0.14/1M (DeepSeek cache miss) = **$0.56**
- With RAG: ~650K schema tokens + ~$0.04 embedding = **$0.13**
- Savings: **~$0.43/month** (for DeepSeek pricing)

> Note: Cost savings are modest at current scale. The primary benefit is **query accuracy improvement** and **schema size scalability**.

---

## 7. Rollback & Safety

- `RAGConfig.enabled = False` restores exact original behaviour
- RAG is a **drop-in replacement** for `build_schema_prompt()` — same return type
- If embedding service is unreachable, fall back to full schema injection
- Vector store is ephemeral (rebuilt from SQLite data) — no migration needed

---

## 8. Open Questions

1. **Embedding provider**: OpenAI `text-embedding-3-small` is the recommended default. Confirm API key availability?
2. **top-k default**: 5 seems right for most shuyu users. Too many tables dilute the RAG benefit; too few miss relevant tables.
3. **Column-level vs table-level retrieval**: Table-level is simpler and covers most use cases. Column-level retrieval adds precision but increases complexity. Start with table-level.
4. **DeepSeek embedding workaround**: DeepSeek has no embedding API. The RAG system must use a separate provider (OpenAI / SiliconFlow / local) regardless.

---

## 9. Visual Diagrams

See companion HTML files in this directory:

- `architecture-comparison.html` — Side-by-side current vs RAG architecture
- `flow-comparison.html` — Request flow: with and without RAG
