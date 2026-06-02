# Changelog

## 2026-06-02 — RAG 全功能实现（Phase 1-6 + 集成测试）

**总览**: 6 个 Phase 全部完成。新增 16 个文件，修改 8 个文件，新增 324 个测试（全部通过），零回归。

### Phase 1：Admin 配置 + ConfigDB 支持

**动机**: 为语义 Schema 检索（RAG）功能奠定配置基础。管理员可在 UI 中启用/配置 RAG，配置存储在 ConfigDB 中。

**变更清单**:

1. **新增 `backend/app/config.py` — `RAGConfig` Pydantic 模型**:
   - `enabled`/`provider`/`model`/`api_key`/`api_base`/`top_k`/`min_score`/`self_learn` 字段
   - 默认值：disabled, provider=openai, model=text-embedding-3-small, top_k=5, min_score=0.3
   - 环境变量覆盖：`RAG_ENABLED` / `RAG_PROVIDER` / `RAG_MODEL` / `RAG_TOP_K`

2. **更新 `backend/app/admin_config/service.py`**:
   - `DEFAULT_SYSTEM_CONFIG` 新增 `"rag"` 段（与 llm/safety/advanced/storage 并列）
   - `update_system_config()` 新增 RAG 配置写⼊逻辑 + API Key 加密存储
   - `get_system_config()` 新增 RAG API Key 解密读取
   - `get_system_config_masked()` 新增 RAG API Key 脱敏显示

3. **更新 `frontend/src/types/index.ts`**:
   - 新增 `RAGConfig` 接口
   - `SystemConfig` 新增可选 `rag: RAGConfig` 字段

4. **新增 `frontend/src/pages/AdminSettings/tabs/RAGSettingsTab.tsx`**:
   - Toggle 开关（启用/禁用 RAG）
   - Provider 下拉（OpenAI / SiliconFlow）
   - 模型、API Key（密码框）、API Base 输入
   - Top-K、最低相似度分数参数
   - 自学习开关（Phase 5 预留）
   - 遵循现有 Admin Tab 设计模式（SettingSection/ToggleRow/PageHeader）

5. **更新 `frontend/src/pages/AdminSettingsPage.tsx`**:
   - 新增 `'rag'` Tab 类型
   - 在 system 分组添加"RAG 配置"导航项
   - 添加 `<RAGSettingsTab />` 渲染

6. **新增 `backend/tests/test_rag_config.py`**（11 个测试）:
   - `TestRAGConfigModel`: 默认值、在 Config 对象中的嵌套、自定义值
   - `TestRAGInSystemConfig`: DEFAULT_SYSTEM_CONFIG 包含 rag、读写、不影响其他段、API Key 脱敏、changelog
   - `TestRAGConfigApiBaseWhitelist`: 合法 URL 接受

**向量存储**: 使用 ChromaDB（`chromadb>=0.5.0` 已在 requirements.txt 中），通过 `PersistentClient` 持久化到 `backend/data/chromadb/`

### Phase 2：向量存储 + Embedding 服务

1. **新增 `backend/app/persistence/vector_store.py`** — ChromaDB 封装：
   - 使用 `chromadb.PersistentClient`，collection `shuyu_rag`，hnsw:space=cosine
   - `upsert_table` / `upsert_batch_tables` / `upsert_column` — 单条/批量写入
   - `search_tables` — 按 database_id + type 过滤的向量检索（min_score 过滤）
   - `delete_database` — 级联删除整个 database 的所有向量

2. **新增 `backend/app/embedding/service.py`** — Embedding 服务抽象：
   - `EmbeddingService` ABC + `OpenAIEmbeddingService` + `SiliconFlowEmbeddingService`
   - `create_embedding_service()` 工厂函数

3. **更新 `backend/app/client.py`** — 新增 `get_embedding_service()` / `reset_embedding_service()` 工厂

4. **新增测试**：`test_vector_store.py`（9 测）、`test_embedding_service.py`（7 测）

### Phase 3：Schema 检索 + Chat 注入

1. **新增 `backend/app/router/schema_retriever.py`** — 检索管道：
   - `init_rag()` — 启动时注入全局实例
   - `rebuild_embeddings()` — Schema 导入后自动重建嵌入
   - `retrieve_schema()` — embed → search → format（含 fallback 机制）

2. **新增 `backend/app/metrics/rag_metrics.py`** — 轻量级线程安全计数器

3. **更新 `backend/app/routes/chat.py`** — 集成 RAG：
   - `_get_rag_enabled()` — 5s TTL ConfigDB 缓存（多 worker 安全）
   - `_get_schema_prompt()` — RAG/全量 Schema 路由
   - POST /api/chat 和 POST /api/chat/stream 双端生效

4. **新增测试**：`test_schema_retriever.py`（8 测）

### Phase 4：生产加固

1. **更新 `backend/app/main.py`** — lifespan 中读取 ConfigDB RAG 配置，自动初始化 VectorStore + EmbeddingService + init_rag()

2. **更新 `backend/app/admin_config/router.py`**：
   - `GET /api/admin/rag/stats` — 运行时 RAG 度量
   - `POST /api/admin/rag/test` — 测试 Embedding 连接

3. **新增测试**：`test_startup_sync.py`（3 测）

### Phase 5：自学习系统

1. **新增 `backend/app/router/question_learner.py`** — Fire-and-forget 自学习：
   - 成功查询后 LLM 生成假设性问题 → embedding → 存入 ChromaDB（Tier 2）
   - 完全非阻塞，静默吞掉所有错误

2. **更新 `backend/app/persistence/vector_store.py`** — 新增 `store_hypothesis()` / `search_hypotheses()` / `delete_hypotheses()`

3. **更新 `backend/app/router/schema_retriever.py`** — Tier 2 优先检索（self_learn 启用时先查假设性问题）

4. **更新 `backend/app/routes/chat.py`** — 查询成功后 `asyncio.ensure_future(learn())`

5. **新增测试**：`test_question_learner.py`（6 测）

### Phase 6：隐私合规 + 完善

1. **更新 `backend/app/persistence/vector_store.py`** — `delete_hypotheses()` 按 database_id 删除用户数据

2. **更新 `backend/app/routes/chat.py`** — `POST /api/user/rag/forget` 删除自学习数据

3. **新增测试**：`test_privacy.py`（3 测）

### 集成测试

**新增 `backend/tests/test_rag_integration.py`**（20 个集成测试）:
- `TestConfigIntegration`: ConfigDB 读写、API Key 脱敏、跨段隔离、Pydantic 模型
- `TestVectorAndRetrievalIntegration`: embed→store→search→format 完整链路、fallback 路径
- `TestEmbeddingServiceIntegration`: 工厂方法、自定义 API Base
- `TestRagMetricsIntegration`: 度量采集
- `TestQuestionLearnerIntegration`: 自学习守卫条件
- `TestHypothesisStorageIntegration`: Tier 2 存储/检索/隔离/删除

**汇总**: 324 测试通过，1 个预存在的 MySQL 测试失败（无关）。

---

## 2026-06-01 — PostgreSQL 支持

### 新增 PostgreSQL 连接器

**动机**: 扩展系统支持的数据库类型，增加 PostgreSQL 支持，用户可以直接连接 Docker/CVM 中的 PostgreSQL 数据库进行数据分析。

**变更清单**:

1. **新增 `backend/app/db/postgresql.py`** — `PostgreSQLConnector(DatabaseConnector)`
   - 基于 `psycopg2` 实现的连接器，支持 `connect`/`disconnect`/`test_connection`/`get_schema`/`execute`
   - `get_schema()` 从 `information_schema` 查询表和列信息，支持主键识别
   - `execute()` 使用 `RealDictCursor` 返回结果，支持自动 COUNT 计数
   - 支持 `include_tables`/`exclude_tables` 表过滤
   - 默认端口 5432，默认用户 postgres

2. **更新 `backend/requirements.txt`** — 新增 `psycopg2-binary>=2.9.0`

3. **更新 `backend/app/routes/database.py`**:
   - `_create_connector()` — 支持 `"postgres"` 类型创建 PostgreSQLConnector
   - `test_database_connection()` — 支持 `"postgres"` 类型测试连接

4. **更新 `backend/app/routes/chat.py`**:
   - `_create_connector()` — 支持 `"postgres"` 类型创建 PostgreSQLConnector

5. **新增 `backend/tests/test_db_postgresql.py`**（11 个测试）:
   - `test_connect_success` / `test_disconnect` / `test_disconnect_when_not_connected`
   - `test_test_connection_success` / `test_test_connection_failure`
   - `test_get_schema` / `test_get_schema_should_exclude_tables` / `test_get_schema_include_only`
   - `test_execute_select` / `test_execute_empty_result`
   - `test_format_data_type_with_length`

**Docker PostgreSQL 连接信息**:
- 容器名: `pg-crm`（PostgreSQL 16）
- Host: `127.0.0.1:5433`（容器内部映射端口）
- User: `postgres`, Password: `postgres`
- Database: `crm_db`
- 表: `accounts`(9列), `contacts`(9列), `interactions`(8列), `opportunities`(9列)

**验证结果**: 后端 279 测试全部通过，前端 126 测试全部通过。

---

## 2026-05-31 — 历史变更汇总

### 用户认证与配置管理系统 (Phase 1-5)
- 新增 Auth 模块：注册/登录/JWT 鉴权/bcrypt 密码加密，支持 admin 角色
- 新增配置管理 API：系统配置/用户配置/合并逻辑/变更日志
- 前端配置页面：7 个 Tab（LLM/安全/存储/高级/运维看板/用户管理/Prompt 管理）
- UI 布局优化：侧边栏导航、卡片布局、渐入动画、自适应宽度
- **验证**: 后端 47 测试通过，TypeScript 零错误

### MySQL 数据库连接器
- 新增 `backend/app/db/mysql.py` — 基于 PyMySQL 的 MySQL 连接器
- `routes/database.py` + `routes/chat.py` 添加 mysql 类型支持
- 支持表过滤、主键识别、参数化查询
- **文件**: `backend/requirements.txt` 新增 `pymysql`

### LLM Temperature 上限限制
- 默认 max temperature: 1.0 → 0.5（保证数据分析客观性）
- 后端 clamp 强制、前端 slider 动态上限
- **验证**: 120 前端 + 234 后端测试通过

### 前端 API 路径修复
- 移除 Prompt 相关 API 的重复 `/api` 前缀（6 处）
- 修复 `request()` 函数已预加 `/api` 导致的 `/api/api/prompts/...` 错误

### 后端测试新增
- `tests/test_models.py` — 17 个 model 测试（ChatRequest/Response，Session，Config，DB，Schema 等）
- `tests/test_auth_middleware.py` — 14 个中间件测试
- **验证**: 78 项新增测试全部通过

### 系统级安全与工程质量修复
- **SQL注入修复**（3处 f-string → 参数化查询）
- **XSS修复**（`to_html()` 添加 `html.escape`）
- **SQLite线程安全**（`check_same_thread=False`）
- **密码/API Key 加密存储**（新增 `utils/crypto.py`，Fernet AES）
- **`except Exception: pass` 修复**（4处 → 日志输出）
- **CORS 安全加固**（method/header 白名单化）
- **密码策略增强**（最小 8 位 + 字母 + 数字）
- **外键 CASCADE**（`PRAGMA foreign_keys=ON`，delete_user 级联删除）
- **验证**: 后端 337 测试通过

### 补充 Agent 和 Chat 路由测试
- `tests/test_describe_schema_agent.py`（21 个测试）
- `tests/test_routes_chat.py`（8 个集成测试）
- 修复 `_parse_llm_response` 不支持 JSON 数组的 bug
- **验证**: 后端 366 测试通过，全量 492 测试通过

### 数据库 Prompt 统一为 XML 格式
- 重置 6 个类别的 Prompt（system v5→v6, 其余 v1→v2）
- 修复 Prompt 管理页面「展开全部」按钮 CSS 截断（`max-h-32` → `max-h-none`）

### 修复 Plan Prompt 占位符问题
- 删除 PLAN_PROMPT 中的 `{schema_prompt}` 占位符（导致 DuckDB 误用 PostgreSQL 语法）
- 修复 `_is_success_result` 对空结果集的误判

### 字体优化
- Google Fonts 新增加载 Noto Sans SC
- 字体栈扩展：`font-sans` 新增系统字体，`font-kai` 优先级调整
- 修复 macOS Times New Roman 导致方块字的问题
- 移除 `antialiased`，新增 `leading-relaxed` 提升中文可读性

### Store 拆分
- 单体 Store → 3 个独立 Store（`sessionStore`/`configStore`/`uiStore`）
- 减少不必要的组件重渲染
- 向后兼容：`import { useStore } from '../store'` 仍可用

### 前端优化
- 消息 ID 生成：`Date.now()` → `crypto.randomUUID().slice(0, 8)` 避免 ID 冲突
- Sidebar 组件原子化拆分（`SessionItem.tsx` + `DbTableNode.tsx`）
- 全量 Store Selector 模式推行（6 个文件，零解构订阅残留）
- Recharts 数据可视化集成（ChartRenderer：柱状图/折线图/饼图智能检测）
- Index Page 首页设计（品牌展示 + 功能卡片 + 状态概览）
- 系统名称统一为"数语"（5 个组件更新）

---

## 2026-06-01 — 前端组件复用重构

### 新增通用组件
- `PageHeader` — 统一页面标题区（title + subtitle + actions）
- `LoadingState` — 统一加载状态
- `EmptyState` — 统一空状态（图标 + 提示 + 操作按钮）
- `Modal` — 通用模态框（title/subtitle/footer/size/backdropBlur）
- `DataTable<T>` — 泛型表格组件（columns/data/render/emptyMessage）
- `AuthLayout` — 登录/注册页面布局

### 重构文件（15 个文件，+522 -605 行）

| 文件 | 变更 |
|------|------|
| `Common.tsx` | 新增 PageHeader/LoadingState/EmptyState；SettingSection 增加 compact prop |
| `ConfigPanel.tsx` | 内联 Section → SettingSection(compact)；内联 ToggleRow → CheckRow |
| `DBConnectModal.tsx` | 改用 Modal 组件 |
| `LLMSettingsTab.tsx` | ModelDialog 改用 Modal + PageHeader |
| `PromptManagementTab.tsx` | 编辑器改用 Modal |
| `UserManagementTab.tsx` | 改用 PageHeader + DataTable + LoadingState |
| `ConfigLogTab.tsx` | 改用 PageHeader + DataTable + LoadingState |
| `DashboardTab.tsx` | 改用 PageHeader + LoadingState |
| `SafetySettingsTab.tsx` | 改用 PageHeader |
| `AdvancedSettingsTab.tsx` | 改用 PageHeader |
| `StorageSettingsTab.tsx` | 改用 PageHeader |
| `DatabaseManagementTab.tsx` | 样式统一(ink/tea/celadon 色系)；改用 PageHeader/EmptyState/LoadingState |
| `LoginPage.tsx` | 改用 AuthLayout |
| `RegisterPage.tsx` | 改用 AuthLayout |

### 测试
- 126 项前端测试全部通过
- TypeScript 类型检查通过
