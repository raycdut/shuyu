# Shuyu RAG — Trae-Friendly Phases

> 每阶段代码量 80-140 行，独立可测试。
> 做完一阶段再开下一阶段，不用回头改上一阶段的代码。

## 工作流程（Trae 严格按此执行）

每阶段按以下步骤执行，**不跳过、不倒序**：

```
Step 1: 读本阶段 "改的文件" + "测试" 列表
Step 2: 实现代码文件
Step 3: 实现测试文件  
Step 4: 运行测试 → pytest tests/xxx.py -v  全部通过
Step 5: 如果测试失败 → 修代码 → 回到 Step 4
Step 6: 通过后 → git add -A
Step 7: git commit -m "rag phase N: xxx"
Step 8: git push origin feature/enable-rag
Step 9: 等待 GitHub Actions 全部绿色 ✅
Step 10: 只有 Actions 通过后，才能进入下一阶段
```

**禁止**：跳过测试直接 commit、Actions 红色时开始下一阶段、修改上一阶段的代码。

---

## Phase 1：Admin 设置页（120 行代码 + 50 行测试）

**目标**：管理员能在 UI 里看到 RAG 开关并保存配置，虽然 RAG 还不起作用。

### 改的文件

| 文件 | 改动 | 行数 |
|------|------|------|
| `backend/app/config.py` | 加 `RAGConfig` Pydantic model | +10 |
| `backend/app/admin_config/service.py` | `DEFAULT_SYSTEM_CONFIG` 加 `"rag"` 段；`update_system_config()` 处理 rag 写入 + api_base 白名单校验 | +25 |
| `frontend/src/pages/AdminSettings/tabs/RAGSettingsTab.tsx` | 新文件：Toggle + Provider 下拉 + Model 输入 + API Key 输入 + 保存按钮 | +80 |
| `frontend/src/pages/AdminSettings/` | 在导航菜单加 RAG 标签入口 | +5 |

### 测试

| 文件 | 测什么 | 行数 |
|------|--------|------|
| `tests/test_rag_config.py` | 1. api_base白名单：合法URL通过、非法URL拒绝、私有IP拒绝<br>2. RAGConfig 默认值正确<br>3. DEFAULT_SYSTEM_CONFIG 包含 rag 段 | +25 |
| `tests/test_admin_api.py` | 1. PUT /api/admin/config 带 rag 配置返回200<br>2. 保存后 GET 返回 masked key | +25 |

**总行数：~170 行**

### 可验证的效果

```
pytest tests/test_rag_config.py -v
→ 3 passed

pytest tests/test_admin_api.py -v
→ 2 passed
```

### 不包含

- 向量存储（Phase 2）
- 检索逻辑（Phase 3）
- 任何性能或安全优化

---

## Phase 2：向量存储 + Embedding（150 行代码 + 60 行测试）

**目标**：schema 导入时自动建向量，有数据可查。

### 改的文件

| 文件 | 改动 | 行数 |
|------|------|------|
| `backend/app/persistence/vector_store.py` | 新文件：使用 **ChromaDB PersistentClient** 存储表/列向量，支持 upsert / search / delete | +70 |
| `backend/app/embedding/service.py` | 新文件：EmbeddingService 抽象类 + OpenAI / SiliconFlow 云端实现 + 工厂方法 | +60 |

### 测试

| 文件 | 测什么 | 行数 |
|------|--------|------|
| `tests/test_vector_store.py` | 1. 初始化 ChromaDB 持久化客户端<br>2. 插入表向量、按向量搜索<br>3. 按 database_id 元数据过滤<br>4. 删除 database 级联清除 | +35 |
| `tests/test_embedding_service.py` | 1. embed() / embed_batch 正常返回<br>2. embed_batch 保持输入顺序<br>3. 云端 provider 工厂方法返回正确类型 | +30 |

### 关键设计

**向量存储（ChromaDB）**：
- 使用 `chromadb.PersistentClient`，数据持久化到 `backend/data/chromadb/`
- 单个 collection `shuyu_rag`，通过 metadata 字段 `database_id` + `type` 过滤
- 默认使用余弦距离（`hnsw:space = cosine`）
- 无需手动管理索引、维度、序列化——ChromaDB 自动处理

**Embedding Provider**：
- **OpenAI**（默认）：`text-embedding-3-small`，1536 维
- **SiliconFlow**：`BAAI/bge-m3`，1024 维（对中文友好）
- Provider 运行时不依赖本地模型，所有 Provider 走远程 API
- API Key 复用 LLM 的 key（或者单独配置）

### 改的文件（续）

| 文件 | 改动 | 行数 |
|------|------|------|
| `backend/app/main.py` | lifespan 里如果 RAG enabled 就初始化 ChromaDB + 重建向量 | +10 |
| `backend/app/client.py` | 加 `get_embedding_service()` 工厂函数 | +10 |

**总行数：~210 行**

### 可验证的效果

```
pytest tests/test_vector_store.py -v
→ 4 passed

1. 启动服务 → 日志显示 "Rebuilding embeddings for database xxx"
2. ls backend/data/chromadb/ → chroma.sqlite3 存在
```

---

## Phase 3：Schema 检索 + 注入生效（110 行代码 + 60 行测试）

**目标**：RAG 真正起作用，用户查询只看到相关表。

### 改的文件

| 文件 | 改动 | 行数 |
|------|------|------|
| `backend/app/router/schema_retriever.py` | 新文件：`retrieve_schema()` — embed → search(只 Tier 1a 表级) → format( relevant_tables + other_tables 带列名) | +70 |
| `backend/app/routes/chat.py` | `_get_rag_enabled()` 从 ConfigDB 读配置（5s TTL 缓存） + `_get_schema_prompt()` 做路由 | +30 |
| `backend/app/metrics/rag_metrics.py` | 新文件：`RagMetrics` class — `total_queries`, `rag_enabled_queries`, `fallback_count` | +20 |

### 测试

| 文件 | 测什么 | 行数 |
|------|--------|------|
| `tests/test_schema_retriever.py` | 1. Mock embedding 返回固定向量 → 检索出正确的 top-3 表<br>2. other_tables 列名格式正确<br>3. 没有匹配时回退到全量 schema<br>4. RAG 关闭时走原有的 build_schema_prompt | +35 |
| `tests/test_chat_routing.py` | 1. RAG enabled 时调用 retrieve_schema<br>2. RAG disabled 时调用 build_schema_prompt<br>3. ConfigDB 中 toggle 变化后路由切换 | +25 |

**总行数：~170 行**

### 可验证的效果

```
pytest tests/test_schema_retriever.py -v
→ 4 passed

用户查询 "上个月华东区销量排名"
→ agent prompt 只包含相关 3 张表的完整信息 + 其他表的列名
关闭 RAG → 同一个查询 → 所有 30 张表都在 prompt
```

---

## Phase 4：生产加固（40 行代码 + 20 行测试）

**目标**：重启不丢配置、多 worker 一致、可观测。

### 改的文件

| 文件 | 改动 | 行数 |
|------|------|------|
| `backend/app/main.py` | lifespan 里从 ConfigDB 读 RAG 配置并同步（补全） | +5 |
| `backend/app/admin_config/router.py` | 加 `GET /api/admin/rag/stats` | +15 |
| `backend/app/admin_config/service.py` | `update_system_config()` 里 RAG 变更时写 changelog | +15 |
| `backend/app/routes/chat.py` | 5s TTL 缓存确认完整 | +5 |

### 测试

| 文件 | 测什么 | 行数 |
|------|--------|------|
| `tests/test_startup_sync.py` | 1. ConfigDB 有 RAG enabled=true → 启动后 state 正确<br>2. ConfigDB 无 RAG 配置 → 默认 disabled | +10 |
| `tests/test_config_changelog.py` | 1. 修改 RAG 设置 → changelog 有记录<br>2. 不修改 RAG 设置 → 不产生 changelog | +10 |

**总行数：~60 行**

---

## Phase 5：自学习（95 行代码 + 40 行测试）

**目标**：系统越用越聪明。

### 改的文件

| 文件 | 改动 | 行数 |
|------|------|------|
| `backend/app/router/question_learner.py` | 新文件：`learn()` — 基本反馈门控 → LLM 生成假设性问题 → embedding → 存 Tier 2 | +60 |
| `backend/app/persistence/vector_store.py` | 加 `hypothetical_questions` 表 + 90天TTL懒清理 | +20 |
| `backend/app/routes/chat.py` | 成功查询后 fire-and-forget 调用 `learn()` | +5 |
| `backend/app/router/schema_retriever.py` | 检索时加 Tier 2 优先 | +10 |

### 测试

| 文件 | 测什么 | 行数 |
|------|--------|------|
| `tests/test_question_learner.py` | 1. Mock LLM 返回假设性问题 → 正确存入 Tier 2<br>2. SQL 报错 → 不生成假设<br>3. 空结果 → 不生成假设<br>4. 重复假设 → 覆盖而不是重复插入 | +25 |
| `tests/test_tier2_retrieval.py` | 1. Tier 2 有匹配时优先返回<br>2. Tier 2 无匹配时走 Tier 1<br>3. 90 天过期数据被忽略 | +15 |

**总行数：~135 行**

---

## Phase 6：隐私合规 + 完善（35 行代码 + 30 行测试）

**目标**：满足企业数据合规要求。

### 改的文件

| 文件 | 改动 | 行数 |
|------|------|------|
| `backend/app/routes/chat.py` | 加 `POST /api/user/rag/forget` | +15 |
| `backend/app/persistence/vector_store.py` | 加 `delete_hypotheses_by_texts(texts)` | +10 |
| `backend/app/admin_config/service.py` | test embedding 只走白名单 provider | +5 |
| `backend/app/main.py` | 启动时触发过期数据清理 | +5 |

### 测试

| 文件 | 测什么 | 行数 |
|------|--------|------|
| `tests/test_privacy.py` | 1. `POST /api/user/rag/forget` 正确删除用户数据<br>2. 非本人数据不受影响<br>3. 过期数据被懒清理正确移除 | +20 |
| `tests/test_security.py` | 1. test embedding 只对白名单 URL 发起请求<br>2. 私有 IP 被拦截时的错误提示友好 | +10 |

**总行数：~65 行**

---

## 汇总

| Phase | 名称 | 代码行 | 测试行 | 总行数 | 1人天 |
|-------|------|--------|--------|--------|-------|
| 1 | Admin 设置页 | ~120 | ~50 | ~170 | ✅ |
| 2 | 向量存储 + Embedding | ~150 | ~60 | ~210 | ✅ |
| 3 | Schema 检索 + 注入 | ~110 | ~60 | ~170 | ✅ |
| 4 | 生产加固 | ~40 | ~20 | ~60 | ✅ |
| 5 | 自学习 | ~95 | ~40 | ~135 | ✅ |
| 6 | 隐私合规 | ~35 | ~30 | ~65 | ✅ |
| | **合计** | **~550** | **~260** | **~810** | |

**每个阶段独立，自带测试。做完 Phase 1-3（~550 行）就有一个可用的、经过测试的 RAG 系统。**

开始 Phase 1 前，确认以下前置条件：
1. Branch: `feature/enable-rag` 已创建并 push 到 remote
2. GitHub Actions 已配置并能正常运行（至少有一个空的 workflow 能通过）
3. 本地能运行 `pytest`（venv 已激活）
