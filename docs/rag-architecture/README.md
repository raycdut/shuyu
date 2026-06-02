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
- Stores three tiers of embeddings (see §3a for strategy):
  - **Tier 1 — Static embeddings**: Table name + descriptions + column names (built on schema import)
  - **Tier 2 — Hypothetical question embeddings**: Generated from real user queries (self-learning)
  - **Tier 3 — Historical SQL embeddings**: Previous successful SQL queries as retrieval documents
- CRUD: sync on schema import, incremental update, self-learning writeback

#### `router/schema_retriever.py` — On-query retrieval logic

```
Input:  user_question (str)
        active_db_id (str)
        top_k (int, default=5)

Steps:
1. Embed user question → q_vector
2. Hybrid search across all three tiers:
   a. Tier 1: table/column static embeddings
   b. Tier 2: hypothetical question embeddings (from past conversations)
   c. Tier 3: historical SQL embeddings (optional)
3. Merge + rank → top-K results
4. For each matched table, load full column details from SQLite
5. Return formatted schema prompt

Output: formatted schema prompt (same shape as build_schema_prompt())
```

#### `router/question_learner.py` — Self-learning from conversations (NEW)

```
Triggered after EACH successful query execution.
No user-facing latency — runs as a background fire-and-forget task.

Step 1: Collect context from the just-completed request:
  - User's original question
  - The tables actually used (from the executed SQL)
  - The SQL that was executed
  - Whether the user gave positive feedback (thumbs-up, expressed satisfaction)

Step 2: LLM generates hypothetical questions (lightweight, 1-shot):
  "Based on the user question '{question}' and the SQL query '{sql}'
   executed against tables {tables}, generate 2-3 alternative phrasings
   that would lead to the SAME SQL query."

  Examples:
    User: "上个月华东区销量排名"
    SQL:  "SELECT p.name, SUM(o.amount) FROM orders o
           JOIN products p ON o.product_id = p.id
           WHERE o.region = '华东' AND o.order_date >= '2026-05-01'
           GROUP BY p.name ORDER BY SUM(o.amount) DESC"
    Tables: orders, products

    Generated hypothetical questions:
    1. "华东地区上月销售额最高的产品有哪些"
    2. "五月份华东区域的销售排行"
    3. "top selling products in east china last month"

Step 3: Embed + store these questions in Tier 2 of the vector store,
        tagged with the table IDs they reference.

Step 4 (future): On negative feedback (user says "wrong"), de-boost
                 or remove the hypothesis that led to this query.

Effect: Over ~50-100 queries, the system "learns" the semantic space
        of its users — what they mean when they say common phrases.
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
    enabled: bool = False            # Master toggle
    backend: str = "sqlite"          # sqlite | chromadb | faiss
    provider: str = "openai"         # openai | siliconflow | local
    model: str = "text-embedding-3-small"
    top_k: int = 5                   # Tables to retrieve per query
    min_score: float = 0.3           # Minimum similarity threshold
    rebuild_on_import: bool = True   # Auto-rebuild embeddings on schema import
    self_learn: bool = True          # Generate hypothetical questions from queries
    self_learn_min_queries: int = 5  # Min queries before learning kicks in
    tier_weights: list[float] = [1.0, 0.8, 0.5]  # Static, Hypothetical, SQL
```

## 3a. Embedding Strategy: What to Put in the Vector Store

Not all embeddings are equal. What you store determines what you retrieve.

### Strategy comparison

| Strategy | Content per entry | Matches | Misses | Implementation |
|----------|-------------------|---------|--------|----------------|
| **A. Table name + description** | `orders: "订单表，记录金额、区域、日期"` | "订单、销售" | "销量排名、增长趋势" | Simplest |
| **B. Table + all column names** | `orders: "orders 订单表 amount(金额) region(区域) date(日期)"` | "金额、区域" | "增长趋势、同比" | Still simple |
| **C. Per-column embedding** | `orders.amount → "订单金额 销售额"\norders.region → "区域 华东"\norders.date → "日期 时间"` | "销量→amount" "华东→region" | Needs aggregation | More complex |
| **D. Hypothetical questions** | `orders → "上个月华东区销量排名"\norders → "不同区域的业绩对比"` | Most natural user queries | Unseen patterns | Needs generation |
| **E. Self-learning (evolved D)** | Tier 1 (static) + Tier 2 (learnt from real users) over time | Everything real users have asked | Rare edge cases | Best long-term |

### Recommended approach: Hybrid three-tier

```
Tier 1 — Static schema embeddings (built on import)
  Entry per table:  table_name + {description} + {all column names with types}
  Entry per column: table_name.column_name + data_type + {description} + {sample values}
  → These NEVER change unless schema is re-imported

Tier 2 — Hypothetical question embeddings (self-learning)
  Generated from real user conversations after each successful query
  → These GROW over time, adapting to how real users phrase things
  → Tagged with the table IDs they resolve to

Tier 3 — Historical SQL embeddings (optional, Phase 3+)
  Successful SQL queries as searchable documents
  → Useful for "I've asked something like this before" scenarios
```

### Why self-learning matters for shuyu

In a Text-to-SQL system, the gap between "what users say" and "what the schema says" is wide:

| User says | Schema has | Gap |
|-----------|-----------|-----|
| "销量" | orders.amount | ✅ Close enough |
| "上个月的业绩" | orders.amount, orders.date | ⚠️ 需要推理时间过滤 |
| "看看这个月的趋势" | orders.amount, orders.date | ⚠️ "趋势"≠任何列名 |
| "有没有什么异常" | Nothing matches | ❌ 完全不在 schema 里 |

The self-learning mechanism closes this gap:

```
First time:
  User: "看看这个月的趋势" 
  → Agent works hard, generates correct SQL (amount + date + GROUP BY month)
  → question_learner.py generates:
    "这个月销售额的趋势是什么"
    "本月各日期的销售额变化"
    "monthly sales trend this month"
  → Stores as Tier 2 embeddings pointing to orders.amount + orders.date

Second time (another user, same DB):
  User: "看看这个月的趋势"
  → RAG finds Tier 2 match directly (score 0.94)
  → Relevant schema retrieved instantly
  → Agent has less work to do, better SQL
```

After ~100 queries, the system effectively has a "FAQ index" of common user questions mapped directly to database schema.

### Implementation note: Tier 2 storage

Tier 2 entries are stored in the same vector store but with a `source='hypothetical'` tag:

```sql
-- In vector_store.py
CREATE TABLE hypothetical_questions (
    id          TEXT PRIMARY KEY,
    database_id TEXT NOT NULL,
    question    TEXT NOT NULL,       -- The hypothetical question text
    table_ids   TEXT NOT NULL,       -- JSON array of referenced table IDs
    source_query TEXT,               -- The original SQL that inspired this
    embedding   BLOB NOT NULL,
    dim         INTEGER NOT NULL,
    hits        INTEGER DEFAULT 0,  -- How many times this hypothesis was retrieved
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
```

The `hits` counter allows pruning: rarely-hit hypotheses get garbage-collected after N days.

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

### Phase 4 — Self-Learning System (Effort: ~2-3 days)

**Goal**: shuyu learns from every user query and gets smarter over time.

| Step | File | Change |
|------|------|--------|
| 1 | `router/question_learner.py` | Create: after-query pipeline to generate hypothetical questions |
| 2 | `persistence/vector_store.py` | Add `hypothetical_questions` table, CRUD, search method |
| 3 | `router/schema_retriever.py` | Hybrid search: merge Tier 1 + Tier 2 results with weighted scoring |
| 4 | `routes/chat.py` | Fire-and-forget call to `question_learner.learn()` after each successful chat |
| 5 | `config.py` | Add `self_learn`, `self_learn_min_queries`, `tier_weights` config fields |

**Self-learning flow per query:**

```
User: "上个月华东区销量排名"
  → Agent queries database using orders + products
  → Return result to user
  ──▶ (background, no blocking)────
      question_learner.learn(
          question="上个月华东区销量排名",
          sql="SELECT ... FROM orders o JOIN products p ...",
          tables=["orders", "products"],
          success=True
      )
      → LLM generates 2-3 hypothetical questions
      → Embed + store in Tier 2 vector store
      → Next similar query hits Tier 2 directly
```

### Phase 5 — Feedback Loop & Pruning (Future)

| Step | Change |
|------|--------|
| 1 | Add "thumbs up/down" UI to shuyu frontend |
| 2 | On thumbs down: de-boost or remove the hypothesis that led to bad SQL |
| 3 | Garbage collection: prune Tier 2 entries with `hits = 0` after 30 days |
| 4 | Admin dashboard: show "most frequently retrieved hypotheses" |

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

## 8. Open Questions (Resolved)

1. ✅ **Embedding provider**: OpenAI `text-embedding-3-small` is the recommended default. DeepSeek has no embedding API.
2. ✅ **top-k default**: 5 for Tier 1. No limit on Tier 2 (hypothetical questions are already sparse and precise).
3. ✅ **Table-level vs column-level**: Both. Tier 1 uses per-table embeddings (simpler), Tier 2 uses per-question embeddings (naturally maps to tables).
4. ✅ **Self-learning**: Yes. `question_learner.py` generates hypothetical questions from real user queries post-chat.
5. ❓ **Feedback UI**: Thumbs up/down in frontend? Would enable pruning bad hypotheses. Consider Phase 5.
6. ❓ **Tier 2 hit count pruning**: Auto-clean hypotheses that never get retrieved. 30-day TTL for zero-hit entries.

---

## 9. Visual Diagrams

See companion HTML files in this directory:

- `architecture-comparison.html` — Side-by-side current vs RAG architecture
- `flow-comparison.html` — Request flow: with and without RAG
