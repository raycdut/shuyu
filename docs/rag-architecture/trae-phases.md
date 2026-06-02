# Shuyu RAG — Trae-Friendly Phases

> 每阶段代码量 80-140 行，独立可测试。
> 做完一阶段再开下一阶段，不用回头改上一阶段的代码。

---

## Phase 1：Admin 设置页（80 行后端 + 80 行前端）

**目标**：管理员能在 UI 里看到 RAG 开关并保存配置，虽然 RAG 还不起作用。

### 改的文件

| 文件 | 改动 | 行数 |
|------|------|------|
| `backend/app/config.py` | 加 `RAGConfig` Pydantic model | +10 |
| `backend/app/admin_config/service.py` | `DEFAULT_SYSTEM_CONFIG` 加 `"rag"` 段；`update_system_config()` 处理 rag 写入 + api_base 白名单校验 | +25 |
| `backend/app/admin_config/router.py` | 无改动（已有的 GET/PUT /api/admin/config 已覆盖） | 0 |
| `frontend/src/pages/AdminSettings/tabs/RAGSettingsTab.tsx` | 新文件：Toggle + Provider 下拉 + Model 输入 + API Key 输入 + 保存按钮 | +80 |
| `frontend/src/pages/AdminSettings/` | 在导航菜单加 RAG 标签入口 | +5 |

**总行数：~120 行**

### 可验证的效果

```
管理员登录 /admin → 看到 RAG Settings 标签页
→ Enable RAG ON → 选 SiliconFlow → 填 key → 保存
→ API 返回 200，配置存到 ConfigDB
→ 重新打开页面，toggle 保持 ON
```

### 不包含

- 向量存储（Phase 2）
- 检索逻辑（Phase 3）
- 任何性能或安全优化

---

## Phase 2：向量存储 + Embedding（130 行）

**目标**：schema 导入时自动建向量，有数据可查。

### 改的文件

| 文件 | 改动 | 行数 |
|------|------|------|
| `backend/app/persistence/vector_store.py` | 新文件：SQLite 表 CREATE、upsert_table、search_tables（余弦相似度）、delete_database | +80 |
| `backend/app/embedding/service.py` | 新文件：EmbeddingService 抽象类 + OpenAI/SiliconFlow 实现 + 工厂方法 | +50 |
| `backend/app/main.py` | lifespan 里如果 RAG enabled 就初始化 embedding 服务 + 重建向量 | +10 |
| `backend/app/client.py` | 加 `get_embedding_service()` 工厂函数 | +10 |

**总行数：~150 行**

### 可验证的效果

```
1. 启动服务 → 日志显示 "Rebuilding embeddings for database xxx"
2. 检查数据库：
   sqlite3 backend/data/vectors.db
   SELECT count(*) FROM table_embeddings;  → 30
3. 重新导入 schema → 向量重建（日志可见）
```

### 不包含

- 检索/注入（Phase 3）
- 多 worker 安全（Phase 4）
- 自学习（Phase 5）

---

## Phase 3：Schema 检索 + 注入生效（110 行）

**目标**：RAG 真正起作用，用户查询只看到相关表。

### 改的文件

| 文件 | 改动 | 行数 |
|------|------|------|
| `backend/app/router/schema_retriever.py` | 新文件：`retrieve_schema()` — embed → search(只 Tier 1a 表级) → format( relevant_tables + other_tables 带列名) | +70 |
| `backend/app/routes/chat.py` | `_get_rag_enabled()` 从 ConfigDB 读配置（5s TTL 缓存） + `_get_schema_prompt()` 做路由 | +30 |
| `backend/app/metrics/rag_metrics.py` | 新文件：`RagMetrics` class — `total_queries`, `rag_enabled_queries`, `fallback_count` | +20 |

**总行数：~120 行**

### 可验证的效果

```
用户查询 "上个月华东区销量排名"
→ 日志：RAG: retrieved 3 tables (orders, products, regions), 12 other_tables
→ agent prompt 里只有这 3 张表的完整信息 + 其他表的列名

关闭 RAG → 同一个查询 → 所有 30 张表都在 prompt 里
```

### 不包含

- 多 worker 优化（Phase 4）
- 自学习（Phase 5）
- 审计日志（Phase 4）

---

## Phase 4：生产加固（50 行）

**目标**：重启不丢配置、多 worker 一致、可观测。

### 改的文件

| 文件 | 改动 | 行数 |
|------|------|------|
| `backend/app/main.py` | lifespan 里从 ConfigDB 读 RAG 配置并同步（已有时不完整，补全） | +5 |
| `backend/app/admin_config/router.py` | 加 `GET /api/admin/rag/stats`（返回 RagMetrics 数据） | +15 |
| `backend/app/admin_config/service.py` | `update_system_config()` 里 RAG 变更时写 changelog | +15 |
| `backend/app/routes/chat.py` | 已有的 5s TTL 缓存确认完整 | +5 |

**总行数：~40 行**

### 可验证的效果

```
1. 管理员 toggle RAG → 重启服务 → RAG 状态保持
2. GET /api/admin/rag/stats 返回:
   {"total_queries": 150, "rag_enabled": true, "fallback_count": 3}
3. ConfigChangelog 表有记录:
   "admin 更新 RAG 配置: enabled=true"
```

### 不包含

- 自学习（Phase 5）
- 用户隐私删除（Phase 6）

---

## Phase 5：自学习（80 行）

**目标**：系统越用越聪明。

### 改的文件

| 文件 | 改动 | 行数 |
|------|------|------|
| `backend/app/router/question_learner.py` | 新文件：`learn()` — 基本反馈门控(SQL 报错/空结果不学) → LLM 生成 2-3 个假设性问题 → embedding → 存 Tier 2 | +60 |
| `backend/app/persistence/vector_store.py` | 加 `hypothetical_questions` 表 + store_hypothesis + search_hypotheses + 90天TTL懒清理 | +20 |
| `backend/app/routes/chat.py` | 成功查询后 fire-and-forget 调用 `question_learner.learn()` | +5 |
| `backend/app/router/schema_retriever.py` | 检索时加 Tier 2 优先（如果有命中且 score > 0.7 就用） | +10 |

**总行数：~95 行**

### 可验证的效果

```
前 3 天：用户问 "上个月的业绩" → 走 Tier 1 → 命中正确表
第 4 天：用户问 "上个月的业绩" → 日志显示 "Tier 2 HIT! score=0.89"
管理员看 /api/admin/rag/stats → "tier2_hit_count": 5
```

### 不包含

- 延迟提交 + 隐式否定检测（太复杂，等用户反馈再决定加不加）
- 用户删除 API（Phase 6）

---

## Phase 6：隐私合规 + 完善（40 行）

**目标**：满足企业数据合规要求。

### 改的文件

| 文件 | 改动 | 行数 |
|------|------|------|
| `backend/app/admin_config/router.py` | 加 `POST /api/user/rag/forget` — 删除当前用户关联的 Tier 2 数据 | +15 |
| `backend/app/persistence/vector_store.py` | 加 `delete_hypotheses_by_texts(texts)` 方法 | +10 |
| `backend/app/admin_config/service.py` | test embedding 只走白名单 provider（已有时补上校验逻辑） | +5 |
| `backend/app/main.py` | 启动时清理过期 Tier 2 数据（懒清理的触发） | +5 |

**总行数：~35 行**

### 可验证的效果

```
用户点击 "清除我的学习数据" → POST /api/user/rag/forget → 200
→ 该用户的查询不再触发 Tier 2 命中
→ Tier 2 表里删除了对应的行
```

---

## Phase 7：自动化测试（180 行）

**目标**：可以放心改代码了。

### 改的文件

| 文件 | 行数 |
|------|------|
| `tests/test_vector_store.py` — 增删查、cos-sim 计算、dim 校验 | +60 |
| `tests/test_schema_retriever.py` — mock embedding → 检索 → 格式化输出 | +50 |
| `tests/test_rag_config.py` — api_base 白名单、参数校验 | +30 |
| `tests/test_regression.py` — RAG 开 vs 关，同一个问题 SQL 质量 | +40 |

**总行数：~180 行**

### 可验证的效果

```
pytest tests/ -v
→ 14 passed in 3.42s
```

---

## 汇总

| Phase | 名称 | 行数 | 单独可跑 | 1人天 |
|-------|------|------|---------|-------|
| 1 | Admin 设置页 | ~120 | ✅ 可配置 | ✅ |
| 2 | 向量存储 + Embedding | ~150 | ✅ schema 被索引 | ✅ |
| 3 | Schema 检索 + 注入 | ~120 | ✅ RAG 真正工作 | ✅ |
| 4 | 生产加固 | ~40 | ✅ 重启/多worker安全 | ✅ |
| 5 | 自学习 | ~95 | ✅ 越用越聪明 | ✅ |
| 6 | 隐私合规 | ~35 | ✅ 满足企业合规 | ✅ |
| 7 | 自动化测试 | ~180 | ✅ 可回归 | ⚠️ 2天 |
| | **合计** | **~740** | | |

**每个阶段独立，互不依赖。做不完 Phase 5-7，Phase 1-4 已经是一个能用的 RAG 系统。**

要不要先从 Phase 1 开始？
