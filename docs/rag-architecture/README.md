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
2. **Layered retrieval** (not flat merge — scores across tiers are not comparable):
   a. **First**: Search Tier 2 (hypothetical questions). These are expressed in
      natural user language, so cosine similarity is most reliable here.
      → If Tier 2 finds matches above `tier2_min_score` (default 0.7), use them.
   b. **If not enough**: Search Tier 1a (table-level). Lower scores expected (0.3-0.6).
   c. **If still not enough**: Search Tier 1b (column-level) for fine-grained matching.
      → For each relevant table, rank columns by similarity to the user question.
      → Only keep columns above `column_min_score` (default 0.5).
      → Example: "上个月华东区销量" → orders.amount(0.89), orders.region(0.82),
        orders.order_date(0.75), orders.product_id(0.31→filtered)
      → This reduces irrelevant columns per table from 15 to 3-5.
   d. **Optional**: Search Tier 3 (historical SQL).
3. Merge results across tiers: Tier 2 results are trusted most, followed by
   Tier 1a, then Tier 1b. De-duplicate by table_id.
4. Take top-K results (K = top_k).
5. For each matched table, load full column details from SQLite.
6. Build **two-part output**:
   a. `<relevant_tables>` — Top-K table schemas with full column details
      (types, descriptions, sample values — enough to write complete SQL)
   b. `<other_tables>` — Remaining tables with column NAMES only
      (no types, no descriptions, no samples — just enough to inform
      the LLM about table shape without bloating the prompt)
      
   Example output:
   ```xml
   <database name="sales_db">
     <relevant_tables>
       表: orders
         - id: INTEGER (PK)
         - amount: DECIMAL(10,2) — 交易金额, 销售额
         - region: VARCHAR(50) — 区域
         - order_date: DATE — 下单日期
       表: products
         - id: INTEGER (PK)
         - name: VARCHAR(100) — 产品名称
     </relevant_tables>
     <other_tables>
       表: suppliers — 供应商信息 (columns: id, name, contact, phone)
       表: inventory — 库存 (columns: id, product_id, qty)
     </other_tables>
     <instructions>
       - 优先使用 relevant_tables 中的表
       - 如果查询需要用到 other_tables 中的表，也可以使用
       - other_tables 只列出了列名，没有详细类型信息，
         请基于列名推断表的结构并谨慎生成 SQL
     </instructions>
   </database>
   ```

**Why column names, not just table names**: Without column names, the LLM
hallucinates column names for `other_tables` (e.g. assumes `suppliers`
has column `contact_person` when it's actually named `contact_phone`).
Column names alone (~5-10 tokens per table) provide enough guidance
without the full schema cost.

**Why no types**: Types add ~20-40 tokens per column. For the 25 tables
not in top-5, that's 500-1000 unnecessary tokens per query. Column names
are sufficient for the LLM to decide "yes I need this table" and then
the SQL engine will validate types at execution time.
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

Step 2: **Feedback gate** — only learn from queries when:
  a. SQL executed without error (required)
  b. Result returned > 0 rows (prevents learning from empty-result queries)
  c. Agent did NOT enter loop-detection before this query (sign of confusion)
  d. Query used at least one table from the Top-5 retrieved (if query used a
     table that wasn't retrieved, the RAG system was wrong — don't reinforce it)
  e. (Future) User gave explicit thumbs-up

  If any gate fails → skip. Do NOT generate hypothetical questions.
  Better to learn nothing than to learn wrong patterns.

Step 3: **Deferred commit** — hypotheses are NOT stored immediately.
  Instead they are placed in a **pending store** within the session:

  ```python
  session.metadata["_pending_hypotheses"] = [
      {"question": "华东地区上月销售额最高的产品有哪些",
       "sql": "SELECT ...", "tables": ["orders", "products"]},
      ...
  ]
  ```

  The session continues. The hypotheses are only "committed" to Tier 2
  when the session ends with a positive signal, OR cleared if the user
  expresses dissatisfaction.

  **Implicit negation detection** (at session end or next user message):
  - Scan the user's next message for negation keywords:
    `"不对", "不是", "错了", "我要的不是", "wrong", "not what I asked"`
  - If negation found → `user_satisfied = false` → discard pending hypotheses
  - If user asks a follow-up question on the SAME topic (e.g. "按产品细分")
    → `user_satisfied = true` → commit pending hypotheses to Tier 2
  - If session times out with no further messages → commit after 24h TTL
    (conservative: assume it was correct)

Step 4: On commit, LLM generates hypothetical questions:
  "Based on the user question '{question}' and the SQL query '{sql}'
   executed against tables {tables}, generate 2-3 alternative phrasings
   that would lead to the SAME SQL query.
   IMPORTANT: Make them diverse — different sentence structures, different
   keywords, different levels of detail. One line per phrasing. No numbering."

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

**Provider config guidance**:
- shuyu's main LLM is DeepSeek, which has NO embedding API.
- **Recommended**: Use **SiliconFlow** (国内直连, 兼容 OpenAI SDK, BGE-M3 中文好).
  → Can reuse an existing SiliconFlow API key or get a free one.
  → Only needs `RAG_PROVIDER=siliconflow` + `RAG_API_KEY` in config.
- **Alternative**: OpenAI `text-embedding-3-small`.
  → Requires a separate OpenAI API key.
- **Simplest setup**: SiliconFlow with the model `BAAI/bge-m3`.
  → Set `RAG_PROVIDER=siliconflow`, `RAG_MODEL=BAAI/bge-m3`, no key needed if using free tier.
- Embedding and chat use SEPARATE API keys and base URLs.
  → Config handles this with `rag.api_key` and `rag.api_base` fields distinct from `llm.*`.

### 3.3 Configuration additions (config.py)

```python
class RAGConfig(BaseModel):
    enabled: bool = False            # Master toggle
    backend: str = "sqlite"          # sqlite | chromadb | faiss
    provider: str = "siliconflow"    # siliconflow (default) | openai | local
    model: str = "BAAI/bge-m3"       # text-embedding-3-small for OpenAI
    api_key: str = ""                # Separate from llm.api_key
    api_base: Optional[str] = None   # e.g. https://api.siliconflow.cn/v1
    top_k: int = 5                   # Tables to retrieve per query
    min_score_tier1: float = 0.30    # Threshold for Tier 1 (table/column)
    min_score_tier2: float = 0.70    # Threshold for Tier 2 (hypothetical)
    # min_score values are defaults — the system auto-tunes based on
    # embedding provider's score distribution (OpenAI scores are higher
    # than BGE scores). Auto-tuning: sample 50 queries, compute mean
    # and std of match scores, set threshold = mean - 0.5*std.
    rebuild_on_import: bool = True   # Auto-rebuild embeddings on schema import
    self_learn: bool = True          # Generate hypothetical questions from queries
    self_learn_gates: bool = True    # Enable feedback gates (P0 safety)
    tier2_max_age_days: int = 90     # Prune unused Tier 2 entries after N days
```

### 3b. Admin Settings Integration

RAG is an **advanced admin-only feature**. It is NOT configured via config.yaml.
Instead, it follows shuyu's existing admin config system:

```
Admin Settings Page (/admin)
  └── RAG Settings tab (NEW)
       ├── Enable RAG                    [toggle]
       ├── Embedding Provider            [dropdown: SiliconFlow | OpenAI | Local]
       ├── Model                         [text: BAAI/bge-m3]
       ├── API Key                       [password field]
       ├── API Base URL                  [text: https://api.siliconflow.cn/v1]
       ├── Top-K (tables to retrieve)    [number: default 5]
       ├── Self-Learning                 [toggle: default ON]
       └── [Test Embedding] button       → API /api/admin/rag/test
```

#### Config storage

RAG settings live in the existing `SystemConfig` JSON blob under a `"rag"` key:

```json
{
  "llm": { ... },
  "safety": { ... },
  "advanced": { ... },
  "rag": {
    "enabled": false,
    "provider": "siliconflow",
    "model": "BAAI/bge-m3",
    "api_key": "(encrypted)",
    "api_base": "https://api.siliconflow.cn/v1",
    "top_k": 5,
    "min_score_tier1": 0.30,
    "min_score_tier2": 0.70,
    "self_learn": true,
    "self_learn_gates": true,
    "tier2_max_age_days": 90
  }
}
```

- API key is encrypted at rest (same mechanism as LLM API keys, via `encrypt_value()`)
- `GET /api/admin/config` returns masked key (`sk-••••abcd`)
- `PUT /api/admin/config` with `{ "rag": { ... } }` updates the RAG section

#### Backend API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /api/admin/config` | GET | Returns full config including `rag` (key masked) |
| `PUT /api/admin/config` | PUT | Save RAG settings alongside other config |
| `POST /api/admin/rag/test` | POST | Test embedding connection with current config |
| `GET /api/admin/rag/stats` | GET | Show vector store stats (#tables, #hypotheses, avg score) |

#### Config → Runtime flow

```
Admin saves RAG settings
  → PUT /api/admin/config { "rag": { "enabled": true, ... } }
  → update_system_config() stores in ConfigDB (encrypted key)
  → If "rag" section changed:
      → Initialize/reinitialize VectorStore
      → If enabled == true:
          → Build Tier 1 embeddings for ALL connected databases
          → Register RAG middleware in chat route
      → If enabled == false:
          → Bypass RAG, use original build_schema_prompt()
  → All subsequent /api/chat requests use new RAG config
```

#### Runtime state synchronization

In `update_system_config()`, when the `"rag"` section changes:

```python
if "rag" in config:
    rag_cfg = merged.get("rag", {})
    state.rag_config.enabled = rag_cfg.get("enabled", False)
    if state.rag_config.enabled and not _rag_initialized:
        embedding_svc = create_embedding_service(...)
        vector_store = VectorStore(...)
        init_rag(embedding_svc, vector_store, state.rag_config)
        for db in state._db_connections:
            asyncio.create_task(rebuild_embeddings(db["id"]))
        _rag_initialized = True
    elif not state.rag_config.enabled:
        _rag_initialized = False
```

#### User experience

- **RAG disabled (default)**: shuyu works exactly as before. Zero change.
- **RAG enabled**: Admin flips the toggle → system builds embeddings in background
  → user messages start getting filtered schema → no restart needed
- **Admin disables RAG**: Instant rollback. Next chat request uses full schema.

---

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
Tier 1a — Table-level embeddings (built on import, Phase 1)
  Entry per table:  table_name + {description} + {all column names with types (compact)}
  → Purpose: Find the right table. "销量" → orders table.
  → ~50-100 tokens per entry. Lightweight, fast.
  → Dimension: 1 vector per table.

Tier 1b — Column-level embeddings (built on import, Phase 1)
  Entry per column: table_name.column_name + data_type + {description} + {sample values}
  → Purpose: Find the right column within a table. "华东" → region column.
  → ~20-50 tokens per entry. Much more precise.
  → Dimension: 1 vector per column. 30 tables × 15 cols = 450 vectors.

  At query time: search both 1a and 1b. Table-level finds the table,
  column-level refines which columns are relevant. Combine results.

  CRITICAL: Splitting table and column levels prevents information dilution.
  A 20-column table's embedding doesn't drown in column noise.

Tier 2 — Hypothetical question embeddings (self-learning, Phase 4)
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
**Config path**: Admin settings page → ConfigDB (NOT config.yaml).

| Step | File | Change |
|------|------|--------|
| 1 | `persistence/vector_store.py` | Create SQLite-backed vector store with numpy cosine similarity |
| 2 | `client.py` | Add `embed()` method alongside `call_llm()` |
| 3 | `router/schema_retriever.py` | Create retrieval pipeline: embed → search → format |
| 4 | `routes/chat.py` | Replace `build_schema_prompt()` with `schema_retriever.retrieve()` when RAG enabled |
| 5 | `admin_config/service.py` | Add `"rag"` to `DEFAULT_SYSTEM_CONFIG`, handle in `update_system_config()` |
| 6 | `admin_config/router.py` | Add `POST /api/admin/rag/test` and `GET /api/admin/rag/stats` endpoints |
| 7 | `frontend/AdminSettings/tabs/` | Add `RAGSettingsTab.tsx` with all fields |
| 8 | `routes/schema.py` | Webhook: auto-rebuild embeddings on schema import |

**Key decision**: RAG config is stored in ConfigDB under `config["rag"]`, encrypted API key.
`config.yaml` only holds the `RAGConfig` Pydantic model definition (defaults), not active values.
Admin saves settings → backend stores in DB → runtime reads from state.

**Architectural must-haves (included in Phase 1)**:

| # | Concern | Solution | Effort |
|---|---------|----------|--------|
| A | Multi-worker state sync | Read RAG config from ConfigDB every query, not from process memory. Add 5s TTL cache. | ~15 lines |
| B | Server restart resets config | Sync RAG config from ConfigDB in `lifespan()`. | ~10 lines |
| C | Concurrent rebuild corrupts data | Atomic swap: build into temp table → DROP + RENAME. File lock to serialize rebuilds. | ~40 lines |
| D | Embedding provider change breaks old vectors | `dim` field on every vector; query only matches same-dim vectors. | ~1 line |
| E | Zero observability | `RagMetrics` class + `GET /api/admin/rag/stats` shows hits, latency, fallback rate. | ~60 lines |
| F | Per-query RAG quality tag | Each response tagged with `rag_info: {mode, tier, score, latency}`. | ~40 lines |

These are not "Phase 2" items — they are foundational. Without them, the system
fails in multi-worker deployment (A) and on restart (B), produces silent data
corruption (C), and has no way to tell if it's working (E).

### Phase 2 — Schema Import Sync (Effort: ~1 day)

| Step | File | Change |
|------|------|--------|
| 1 | `persistence/vector_store.py` | Add `rebuild(db_id)` and `incremental_update()` methods |
| 2 | `agent/describe_schema_agent.py` | After descriptions are generated, trigger embedding rebuild |
| 3 | Database routes | Hook into `/api/database/import` to rebuild embeddings |

### Phase 3 — Multi-Provider, Multi-Turn & Optimization (Effort: ~2-3 days)

| Step | Change |
|------|--------|
| 1 | Add ChromaDB backend (optional, for larger schemas) |
| 2 | Add SiliconFlow / local BGE-M3 support |
| 3 | Embedding cache & batch processing |
| 4 | **Multi-turn RAG strategy**: In a single conversation session, RAG is only
      triggered on the FIRST user message. Subsequent messages reuse the same
      retrieved schema (users refine their queries, not switch topics).
      If the user explicitly mentions a new table or topic, re-trigger RAG.
      → Implementation: store `rag_state = {tier_used, table_ids, question_embedding}`
        in session metadata. Compare new question with stored embedding (cos-sim).
        If below threshold → re-retrieve. |
| 5 | **SQLite + numpy latency optimization**:
      - Add `LIMIT N` to the numpy loop: pre-filter by database_id, then
        apply a fast approximate filter (e.g. dot product > 0.1) before full norm.
      - For Tier 2 with 2000+ entries, add a simple inverted-index pre-filter:
        match keywords from the user question to table descriptions first.
      - If latency exceeds 200ms consistently, move to ChromaDB (Phase 3 backend). |
| 6 | **Dynamic min_score auto-tuning**:
      - After first 50 RAG queries, collect all match scores.
      - Compute mean and std per tier.
      - Set `min_score_tier1 = mean - 0.5*std`, `min_score_tier2 = mean - 0.5*std`.
      - Re-tune every 500 queries.
      - Config field `min_score_tier1` and `min_score_tier2` override auto-tuning. |
| 7 | A/B comparison: RAG vs full-schema on query quality |

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

## 8. Design Review: Resolved Defects

The following defects were identified during design review and have been fixed:

| Severity | Issue | Fix |
|----------|-------|-----|
| **P0** | RAG truncation hides tables from agent | Inject `other_tables` with column NAMES (no types) alongside `relevant_tables` |
| **P0** | Single Tier 1 vector per table dilutes column signal | Split into Tier 1a (table) + Tier 1b (column), both Phase 1. Add column-level score filtering. |
| **P0** | Self-learning reinforces wrong queries | Add deferred commit + implicit negation detection in session. Hypotheses only committed after follow-up confirmation. |
| **P1** | Tier 1/2 scores not comparable | Layered search: Tier 2 first, Tier 1a/1b as fallback. Each tier has its own min_score. |
| **P1** | Two providers = complex config | Default SiliconFlow (BGE-M3), separate `rag.api_key` from `llm.api_key` |
| **P1** | min_score hardcoded | Tier-specific thresholds + auto-tuning after 50 queries |
| **P1** | Multi-worker state inconsistent | Read RAG config from ConfigDB per query (5s TTL cache), not from process memory |
| **P1** | Server restart reverts config | Sync RAG config from ConfigDB in `lifespan()` startup |
| **P1** | No observability | `RagMetrics` class + `GET /api/admin/rag/stats` + per-query `rag_info` tag |
| **P2** | Concurrent rebuild corrupts data | Atomic swap (temp table + DROP/RENAME) + file lock for serialization |
| **P2** | Provider switch breaks vector dims | `dim` field on all vectors; query only matches same-dim vectors |
| **P2** | No multi-turn strategy | First message only; reuse schema in same session unless topic changes |
| **P2** | Hypothetical question diversity | Prompt now enforces diverse phrasings explicitly |
| **P2** | SQLite + numpy O(n) latency | Fast pre-filter, keyword index, escalate to ChromaDB if >200ms |
| **P2** | Self-learning hypotheses stored before validation | Deferred commit: pending hypotheses in session metadata, only committed after user confirmation |

---

## 9. Visual Diagrams

See companion HTML files in this directory:

- `architecture-comparison.html` — Side-by-side current vs RAG architecture
- `flow-comparison.html` — Request flow: with and without RAG
