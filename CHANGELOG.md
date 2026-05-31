# 变更日志

## [2026-05-31] 移除个人数据看板功能

### 背景
决定精简功能范围，聚焦核心能力。`/dashboard` 个人数据看板（用户固定聊天结果到看板）被移除，作为开源软件当前功能已足够。管理员运营看板（AdminSettings DashboardTab）保留。

### 变更内容
移除个人数据看板（Personal Dashboard）的完整链路：前端页面、路由、导航入口、固定交互、API、状态管理、后端路由、数据库表。

#### 删除文件
- **`frontend/src/components/Dashboard.tsx`**: 个人数据看板页面组件
- **`backend/app/routes/dashboard.py`**: 看板 CRUD API（GET/POST/DELETE `/dashboard/items`）

#### 变更文件
| 文件 | 变更 |
|------|------|
| `frontend/src/App.tsx` | 移除 Dashboard 组件导入和 `/dashboard` 路由 |
| `frontend/src/components/AppLayout.tsx` | 移除顶部导航栏看板按钮 |
| `frontend/src/pages/IndexPage.tsx` | 移除首页看板功能卡片 |
| `frontend/src/components/MarkdownRenderer.tsx` | 移除 QueryBadge 中的固定/取消固定按钮及相关逻辑、API 调用、Store 使用 |
| `frontend/src/api/index.ts` | 移除 `getDashboardItems`/`addDashboardItem`/`removeDashboardItem` |
| `frontend/src/store/uiStore.ts` | 移除 `DashboardItem` 接口及所有看板相关的状态和 actions |
| `frontend/src/store/index.ts` | 移除 `DashboardItem` 类型导出 |
| `frontend/src/pages/IndexPage.test.tsx` | 移除看板卡片导航测试；更新渲染测试（不再检查"数据看板"文本） |
| `frontend/src/i18n/locales/zh-CN.json` | 移除 `nav.dashboard`, `nav.dataDashboard`, `dashboard.*`, `chart.removeFromDashboard`, `chart.pinToDashboard`, `index.dashboardTitle/Desc/viewDashboard` |
| `frontend/src/i18n/locales/en-US.json` | 同上英文翻译 |
| `backend/app/main.py` | 移除 `dashboard` 路由导入和注册 |
| `backend/app/persistence/__init__.py` | 移除 `_migrate_dashboard_tables()` 函数和调用 |

#### 保留的功能
- 管理员运营看板 (AdminSettings DashboardTab) — 展示系统运营统计数据
- `GET /admin/stats` API — 为管理员看板提供数据

---

## [2026-05-31] 管理页面 Tab 分组

### 变更内容
将系统管理页面侧边栏的 Tab 按钮按功能划分为 4 个分组，每组有明确的分组标题，便于管理员快速定位。

**分组结构**:

| 分组 | 包含 Tab | 说明 |
|------|---------|------|
| 运营总览 | 运营看板 | 查看平台运营数据 |
| 系统设置 | LLM 提供商、安全设置、存储设置、高级设置 | 核心系统参数配置 |
| 资源管理 | 数据库管理、用户管理 | 数据与用户资源 |
| 运维工具 | Prompt 管理、配置日志 | 日常运维支持 |

#### 变更文件
- **`frontend/src/pages/AdminSettingsPage.tsx`**: TAB_GROUPS 结构替代扁平 TABS 数组，侧边栏渲染分组标题 + 子项
- **`frontend/src/i18n/locales/zh-CN.json`**: 新增 `groupOverview`, `groupSystem`, `groupResources`, `groupOps`
- **`frontend/src/i18n/locales/en-US.json`**: 同上英文翻译

---

## [2026-05-31] 管理员运营看板 (Admin Dashboard)

### 背景
管理员需要实时了解平台运营状况：今日登录用户数、用户提问量、Token 消耗等指标，以便更好地维护和优化系统。

### 变更内容

#### 后端
- **`backend/app/routes/admin_stats.py`** (新增)
  - `GET /api/admin/stats` — 管理员获取系统运营统计数据
  - 返回概览数据（总用户数、总会话数、今日登录数、今日提问数、今日 Token 用量等）
  - 返回趋势数据（近 N 天活跃用户趋势、提问趋势、Token 用量趋势）
  - 返回最活跃用户 Top 10
  - 返回模型用量分布（各模型调用次数、Token 用量、平均 Token/次）
- **`backend/app/main.py`**
  - 注册 `admin_stats` 路由

#### 前端
- **`frontend/src/pages/AdminSettings/tabs/DashboardTab.tsx`** (新增)
  - 运营看板组件，包含概览卡片、趋势迷你柱状图、最活跃用户表格、模型用量表格
- **`frontend/src/pages/AdminSettingsPage.tsx`**
  - 新增 "运营看板" Tab（放在管理页面首位，打开管理页面默认显示）
- **`frontend/src/types/index.ts`**
  - 新增 `OverviewStats`, `TrendPoint`, `TrendsData`, `TopUser`, `ModelUsage`, `AdminStatsResponse` 类型
- **`frontend/src/api/index.ts`**
  - 新增 `getAdminStats()` API 方法
- **`frontend/src/i18n/locales/zh-CN.json`** / **`en-US.json`**
  - 新增 `adminDashboard` 和 `adminSettings.dashboard` 翻译

#### 测试
- **`backend/tests/test_admin_stats_api.py`** (新增)
  - 8 个测试用例覆盖：未认证访问、数据完整性、概览计数、趋势维度、用户排行、模型用量、权限控制、自定义参数

### 涉及的 API 端点变更

| 端点 | 变更类型 | 说明 |
|------|---------|------|
| `GET /api/admin/stats` | 新增 | 管理员运营统计数据（需 admin 权限） |

---

## [2026-05-31] 配置审计日志增强

### 背景
管理页面上所有配置动作（用户管理、数据库管理等）之前缺少配置日志记录，导致无法审计管理员的配置操作。

### 变更内容

#### 数据库
- **`backend/app/persistence/migration_004_expand_config_type.py`** (新增)
  - 迁移 `config_changelog` 表的 `config_type` 约束，从 `('system', 'user')` 扩展为 `('system', 'user', 'user_mgmt', 'database')`
- **`backend/app/persistence/__init__.py`**
  - 调用新的迁移
  - 更新 DDL 中的 CHECK 约束

#### 日志函数
- **`backend/app/admin_config/service.py`**
  - 新增 `log_user_management_change()` — 用户管理操作日志入口
  - 新增 `log_database_change()` — 数据库管理操作日志入口

#### 用户管理日志
- **`backend/app/auth/service.py`**
  - `create_user()`: 记录 `"创建用户: {username} (角色: {role})"`
  - `update_user()`: 记录 `"更新用户: {username} — 角色: old→new; 状态: 启用→禁用"`
  - `delete_user()`: 记录 `"删除用户: {username}"`
  - `set_user_databases()`: 记录 `"为用户 {username} 分配 N 个数据库权限"`
- **`backend/app/auth/router.py`**
  - 从 `require_admin` 中提取管理员用户名并传递给各 service 函数

#### 数据库管理日志 + 鉴权
- **`backend/app/routes/database.py`**
  - 为所有写操作添加 `Depends(require_admin)` 鉴权
  - `POST /api/database/connect`: 记录 `"添加数据库连接: {name} (类型: {type})"`
  - `PATCH /api/database/{id}`: 记录 `"更新数据库连接: {name} — 修改字段: field1, field2"`
  - `DELETE /api/database/{id}`: 记录 `"删除数据库连接: {name}"`
  - `POST /api/database/{id}/schema/import`: 记录 `"导入数据库 Schema: {name} → N 张表"`
  - `POST /api/database/{id}/schema/describe`: 记录 `"AI 生成描述: {name} → N 张表"`
  - `PATCH /api/database/{id}/schema/describe`: 记录 `"更新描述: {name} → 表/字段 {id}"`

#### 测试
- **`backend/tests/test_admin_config_service.py`**: 更新 DDL 约束，修复 3 个预置测试
- **`backend/tests/test_auth_service.py`**: 新增 `config_changelog` 表创建
- **`backend/tests/test_auth_api.py`**: 新增 `config_changelog` 表创建

### 涉及的 API 端点变更

| 端点 | 变更类型 | 说明 |
|------|---------|------|
| `POST /api/database/connect` | 鉴权 + 日志 | 新增 `require_admin` |
| `PATCH /api/database/{id}` | 鉴权 + 日志 | 新增 `require_admin` |
| `DELETE /api/database/{id}` | 鉴权 + 日志 | 新增 `require_admin` |
| `POST /api/database/{id}/schema/import` | 鉴权 + 日志 | 新增 `require_admin` |
| `POST /api/database/{id}/schema/describe` | 鉴权 + 日志 | 新增 `require_admin` |
| `PATCH /api/database/{id}/schema/describe` | 鉴权 + 日志 | 新增 `require_admin` |
| `PATCH /api/admin/users/{id}` | 日志 | 新增配置日志 |
| `DELETE /api/admin/users/{id}` | 日志 | 新增配置日志 |
| `PUT /api/admin/users/{id}/databases` | 日志 | 新增配置日志 |
| `POST /api/auth/register` | 日志 | 新增配置日志 |
