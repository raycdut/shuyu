# Changelog

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
