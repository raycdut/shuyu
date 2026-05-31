# Change Log

## 2026-05-31

### Limited maximum LLM temperature to 0.5 for objective data analysis

**Motivation**: The system's data insights should be absolutely objective. Low temperature (low "warmth") ensures more deterministic, factual outputs rather than creative ones.

**Changes**:

1. **Default max temperature reduced** (`backend/app/admin_config/service.py`):
   - `llm_temperature_range.max`: 1.0 → 0.5 (both `DEFAULT_SYSTEM_CONFIG` and fallback in `get_user_available_options`)

2. **Backend enforcement** (`backend/app/admin_config/service.py`):
   - `update_user_config()`: When saving user preferences, clamps `temperature` to the configured `llm_temperature_range.max`
   - `_merge_configs()`: When merging user preferences into runtime config, clamps temperature to the configured max

3. **Frontend slider limit** (`frontend/src/components/ConfigPanel.tsx`):
   - Temperature slider now reads `tempMax` from `api.getUserAvailableOptions().preferences.temperature.max`
   - Slider `max` changes from hardcoded `"1"` to dynamic `{tempMax}`
   - When the panel opens, temperature is clamped to max

4. **Fixed pre-existing TS error** (`frontend/src/pages/AdminSettings/tabs/AdvancedSettingsTab.tsx`):
   - Added missing `llm_temperature_range` property when saving advanced settings

**Verification**: All 120 frontend tests and 234 backend tests pass.

**Root cause**: Frontend API client had duplicate `/api` prefix in prompt-related API calls. The `request()` function already prepends `BASE = '/api'` to all URLs, but the prompt API paths were hardcoded with `/api/prompts/...`, resulting in double-prefixed URLs (`/api/api/prompts/...`).

**Fix**: Removed the redundant `/api` prefix from all 6 prompt API call paths in `frontend/src/api/index.ts`:
- `getPrompts`: `/api/prompts` → `/prompts`
- `getPrompt`: `/api/prompts/{id}` → `/prompts/{id}`
- `upsertPrompt`: `/api/prompts` → `/prompts`
- `activatePrompt`: `/api/prompts/{id}/activate` → `/prompts/{id}/activate`
- `getActivePrompts`: `/api/prompts/active` → `/prompts/active`
- `getDefaultPrompt`: `/api/prompts/{category}/default` → `/prompts/{category}/default`

**Verification**: All 120 frontend tests and 234 backend tests pass. TypeScript compilation produces no errors.

### Added tests for backend Python source files

Created two comprehensive test files under `backend/tests/`:

#### `tests/test_models.py`
- **TestChatRequest** (6 tests): creation with various params, defaults, empty message, custom mode
- **TestChatResponse** (7 tests): minimal/all fields, default empty lists, missing required fields
- **TestSessionRenameRequest** (3 tests): creation with title, empty title, missing title
- **TestSessionMessagesResponse** (4 tests): creation with messages, empty messages, missing fields
- **TestConfigUpdate** (5 tests): empty/llm-only/safety-only/both updates, nested dicts
- **TestLLMTestResult** (5 tests): success/failure results, empty message, missing fields
- **TestDBConnectRequest** (5 tests): minimal, MySQL connection, file path, connection string, table filters
- **TestDBInfo** (3 tests): minimal, all fields, missing id
- **TestDBTestResult** (3 tests): ok/fail results, missing ok field
- **TestColumnSchema** (3 tests): minimal, all fields, primary key
- **TestTableSchema** (3 tests): minimal, view type, multiple columns
- **TestImportedColumnInfo** (3 tests): minimal, with sample values, empty sample values
- **TestImportedTableInfo** (2 tests): minimal, with nested columns
- **TestSchemaImportRequest** (3 tests): empty, with database_id, with table filters
- **TestDescriptionGenerateRequest** (3 tests): empty, with table_ids, with language and force
- **TestDescriptionUpdateRequest** (3 tests): empty, table description, column description
- **TestSchemaStatusResponse** (3 tests): default values, with values, custom status

#### `tests/test_auth_middleware.py`
- **TestGetCurrentUser** (10 tests): missing/empty/non-bearer auth header, invalid token, user not found, disabled user, valid user/admin, verifies correct arguments passed to mocked functions
- **TestRequireAdmin** (4 tests): admin passes, non-admin raises 403, custom role case, disabled admin

#### Test results
- All 78 tests passed successfully
- Follows existing patterns: pytest classes, SQLite `:memory:` fixtures (where applicable), `from app.xxx import yyy` style, function-level docstrings

## 2026-06-01

### 系统级安全与工程质量修复（全量审查修复）

**动机**: 对系统进行了全方位架构、工程、安全审查，修复了审查中发现的全部 P0 严重问题和主要 P1 问题。

**修复清单**:

#### P0 - 严重问题修复

1. **F-String SQL 注入修复**（3处）:
   - `backend/app/db/duckdb.py:62` — `get_schema()` 中 `WHERE table_name = ?` 参数化查询
   - `backend/app/routes/database.py:104` — `get_database_tables()` 中参数化查询
   - `backend/app/routes/database.py:265` — `import_schema()` 中参数化查询

2. **COUNT(*) 子查询安全加固** (`backend/app/db/duckdb.py:105`):
   - 多语句检测：仅当 SQL 为单语句时执行 `SELECT COUNT(*)` 计数

3. **XSS 修复** (`backend/app/db/base.py:71`):
   - `to_html()` 添加 `html.escape(str(val))` 防止数据库内容中的 XSS 攻击

4. **SQLite 线程安全修复** (`backend/app/persistence/__init__.py:149`):
   - 生产环境 SQLite 连接添加 `check_same_thread=False` 防止多请求并发崩溃

5. **密码/API Key 加密存储**:
   - 新增 `backend/app/utils/crypto.py` — 基于 Fernet (AES) 的对称加密工具，密钥从 `AUTH_SECRET_KEY` 派生
   - `backend/app/persistence/database.py` — 数据库密码保存时加密、加载时解密
   - `backend/app/admin_config/service.py` — LLM API Key 保存时加密、加载时解密
   - `backend/requirements.txt` — 新增 `cryptography>=41.0.0`

6. **`except Exception: pass` 修复**（4处，`backend/app/persistence/__init__.py`）:
   - 全部替换为带 `logger.info()` 的日志输出，明确标注迁移已跳过

#### P1 - 强烈建议修复

7. **CORS 安全加固** (`backend/app/main.py`):
   - `allow_methods` 从 `["*"]` 收紧为白名单 `["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]`
   - `allow_headers` 从 `["*"]` 收紧为 `["Content-Type", "Authorization", "Accept"]`
   - `allow_origins` 支持通过 `CORS_ORIGINS` 环境变量配置

8. **密码策略增强** (`backend/app/auth/router.py`):
   - 最小长度 6 → 8
   - 新增字母和数字要求

9. **外键 CASCADE 完善**:
   - `backend/app/persistence/__init__.py` — 启用 `PRAGMA foreign_keys=ON`
   - `backend/app/auth/service.py` — `delete_user()` 新增级联删除用户会话和消息

#### 验证结果
- 后端 337 测试全部通过（88 根级 + 249 backend/tests）
- 前端 126 测试全部通过
- 总计 463 测试全部通过

### 补充 Agent 和 Chat 路由测试

**动机**: 审查报告中指出 `describe_schema_agent.py`（0 测试）和 `routes/chat.py`（0 集成测试）是测试覆盖缺口，需要补齐。

**新增测试文件**:

1. **`tests/test_describe_schema_agent.py`**（21 个测试）:
   - `TestBuildTableBlock`（5 tests）: 基础表/含描述/示例值/截断/无字段
   - `TestBuildUserPrompt`（2 tests）: 单表/多表
   - `TestParseLlmResponse`（7 tests）: 合法JSON/markdown包裹/空内容/非法JSON/无tables键/dict/无内容
   - `TestGenerateDescriptions`（7 tests）: 无表/指定表ID/完整管线/LLM错误/数据库不存在/批次处理/空table_ids

2. **`backend/tests/test_routes_chat.py`**（8 个测试）:
   - `TestChatRoute`: Agent未初始化503/无API Key/无db_id/Fast模式/Quality模式/Session ID保持/消息持久化/无效db_id

**同时修复的 bug**:
- `_parse_llm_response()` 不支持顶层 JSON 数组格式（不兼容 OpenAI 工具的 `response_format` 输出），已修复

#### 验证结果
- 后端 366 测试全部通过（88 根级 + 278 backend/tests）
- 前端 126 测试全部通过
- 总计 **492 测试全部通过**

### 数据库 Prompt 统一为 XML 格式

**问题**: 代码中的 Prompt 默认模板已统一为 XML 格式（`<instructions>`、`<role>`、`<rules>` 等标签），但数据库中存储的 Prompt 仍是旧的 Markdown 格式（首次启动时 seed 的旧数据）。用户在 Prompt 管理页面看不到变化。

**修复**: 执行 `backend/seeds/reset_prompts.py` 重置脚本，将数据库中全部 6 个类别的 Prompt 重置为代码中的 XML 默认值：
- `system` v5 → v6
- `sql_gen` v1 → v2
- `plan` v1 → v2
- `plan_reflect` v1 → v2
- `report_reflect` v1 → v2
- `schema_describe` v1 → v2

**注意**: 需重启后端服务使新 Prompt 生效。

### 修复 Prompt 管理页面展开按钮无效

**问题**: Prompt 卡片中的「展开全部」按钮点击后，`<pre>` 标签上仍有 `max-h-32 overflow-y-hidden` 样式，导致内容即使显示了完整文本也被 CSS 截断。

**修复**: 展开时动态移除 `overflow-y-hidden` 并将 `max-h-32` 切换为 `max-h-none`。

**文件**: [PromptManagementTab.tsx](frontend/src/pages/AdminSettings/tabs/PromptManagementTab.tsx)
