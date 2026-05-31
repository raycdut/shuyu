# 后台配置页面设计文档

## 1. 概述

当前系统将 LLM 配置、数据安全配置、高级设置全部集中在右侧 `ConfigPanel` 面板中，所有用户（未来多用户环境下）看到的是同一套配置。本文档设计一套**按角色分离**的配置体系，将配置分为两个层级：

| 层级 | 角色 | 范围 | 说明 |
|------|------|------|------|
| **管理员配置** | `admin` | 全局生效 | 系统级设置，仅管理员可修改 |
| **用户配置** | `user` | 个人生效 | 用户个性化设置，在管理员设定的范围内自选 |

### 核心设计原则

- **关注点分离**：管理员关注"系统怎么跑"，用户关注"我用起来顺手"
- **权限下沉**：管理员可限制用户能修改的范围（如只允许用户在管理员指定的模型列表中切换）
- **向前兼容**：单用户模式下（无 auth），所有配置项直接显示在一个页面中

---

## 2. 配置模型

### 2.1 配置分类总览

```
系统配置 (SystemConfig)
├── 全局 LLM 配置 (llm)
│   ├── provider_pool       # 可用提供商列表（admin 定义，user 从中选）
│   └── default_model       # 系统默认模型
├── 全局安全配置 (admin_safety)
│   ├── read_only            # 默认只读模式
│   ├── require_approval     # 默认数据确认
│   ├── max_rows             # 默认最大行数
│   ├── blocked_tables       # 全局屏蔽表
│   └── masked_columns       # 全局脱敏列
├── 全局高级设置 (admin_advanced)
│   ├── session_expire_minutes    # 默认会话过期时间
│   ├── max_sessions_per_user     # 每用户最大会话数
│   ├── allow_user_llm_config     # 是否允许用户自选 LLM
│   ├── allow_user_safety_override  # 是否允许用户覆盖安全设置
│   └── llm_temperature_range     # 温度范围限制 {min, max, default}
└── 存储配置 (storage)            # 保留现有，仅 admin 可见
    ├── log_interval
    └── log_retention_days
```

```
用户配置 (UserConfig)
├── 个人 LLM 选择 (user_llm)
│   ├── provider              # 从 admin 定义的 provider_pool 中选择
│   ├── model                 # 从该提供商可用模型中选择
│   ├── api_key               # 可选：用户自己的 API Key（覆盖全局）
│   ├── api_base              # 可选：用户自定义 endpoint
│   └── timeout               # 用户自定义超时（在 admin 限制范围内）
├── 个人安全设置 (user_safety)
│   ├── read_only             # 覆盖全局（如果 admin 允许）
│   ├── require_approval      # 覆盖全局（如果 admin 允许）
│   └── max_rows              # 覆盖全局（不超过 admin 设定值）
├── 个人偏好 (user_preferences)
│   ├── language              # 界面语言
│   ├── temperature           # 在 admin 限制的范围内调节
│   ├── theme                 # 主题偏好（light/dark）
│   └── default_view          # 默认视图（chat/dashboard）
└── 个人数据 (user_data)
    ├── sessions              # 用户会话列表（现有）
    └── pinned_dashboards     # 用户固定的看板项（现有）
```

### 2.2 数据存储

当前配置存储在 SQLite 的 `config` 表（单行 KV 结构）。新方案扩展为：

```sql
-- 全局系统配置（单行，JSON 存储）
CREATE TABLE IF NOT EXISTS system_config (
    id          INTEGER PRIMARY KEY CHECK (id = 1),  -- 强制单行
    config      TEXT NOT NULL DEFAULT '{}',           -- JSON 格式
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by  TEXT REFERENCES users(id)
);

-- 用户配置（每用户一行）
CREATE TABLE IF NOT EXISTS user_configs (
    user_id     TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    config      TEXT NOT NULL DEFAULT '{}',           -- JSON 格式
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**设计理由**：
- 使用 JSON 字段而非多列，便于版本迭代（新增配置项无需改表结构）
- `system_config` 使用 `CHECK(id = 1)` 约束保证全局唯一行
- `user_configs` 与 `users` 表 CASCADE 关联，删除用户自动清理

---

## 3. 后端 API 设计

### 3.1 系统配置 API（需 admin 权限）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/admin/config` | 获取完整系统配置 |
| `PUT` | `/api/admin/config` | 更新系统配置（全量替换） |
| `PATCH` | `/api/admin/config` | 局部更新系统配置 |

**GET /api/admin/config**

```json
// Response 200
{
  "llm": {
    "provider_pool": [
      { "provider": "openai", "label": "OpenAI", "models": ["gpt-4o", "gpt-4o-mini"], "enabled": true },
      { "provider": "deepseek", "label": "DeepSeek", "models": ["deepseek-v4-flash", "deepseek-v4-pro"], "enabled": true },
      { "provider": "anthropic", "label": "Anthropic", "models": ["claude-3-5-sonnet"], "enabled": false }
    ],
    "default_model": "gpt-4o"
  },
  "safety": {
    "read_only": true,
    "require_approval": true,
    "max_rows": 1000,
    "blocked_tables": [],
    "masked_columns": []
  },
  "advanced": {
    "session_expire_minutes": 1440,
    "max_sessions_per_user": 50,
    "allow_user_llm_config": true,
    "allow_user_safety_override": false,
    "llm_temperature_range": { "min": 0, "max": 1, "default": 0.3 }
  },
  "storage": {
    "log_interval": "day",
    "log_retention_days": 30
  },
  "updated_at": "2025-06-01T12:00:00Z",
  "updated_by": "admin-uuid"
}
```

**PUT /api/admin/config**

```json
// Request — 全量替换
{
  "llm": { ... },
  "safety": { ... },
  "advanced": { ... },
  "storage": { ... }
}

// Response 200 — 返回更新后的完整配置
```

**PATCH /api/admin/config**

```json
// Request — 仅发送需要修改的字段
{
  "safety": { "max_rows": 5000 },
  "advanced": { "allow_user_llm_config": false }
}

// Response 200 — 返回合并后的完整配置
```

### 3.2 用户配置 API（需登录）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/user/config` | 获取当前用户的配置（合并系统默认 + 用户覆盖） |
| `PUT` | `/api/user/config` | 更新当前用户的配置 |
| `GET` | `/api/user/config/available` | 获取用户可选范围（admin 允许的选项列表） |

**GET /api/user/config**

```json
// Response 200 — 合并后的生效配置
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o",
    "api_key": "",
    "api_base": "https://api.openai.com/v1",
    "timeout": 60
  },
  "safety": {
    "read_only": true,
    "require_approval": true,
    "max_rows": 1000
  },
  "preferences": {
    "language": "zh-CN",
    "temperature": 0.3,
    "theme": "light",
    "default_view": "chat"
  }
}
```

**GET /api/user/config/available**

返回当前用户可选择的选项范围（由 admin 配置决定）：

```json
// Response 200
{
  "llm": {
    "providers": [
      { "provider": "openai", "label": "OpenAI", "models": ["gpt-4o", "gpt-4o-mini"] },
      { "provider": "deepseek", "label": "DeepSeek", "models": ["deepseek-v4-flash"] }
    ],
    "can_use_custom_api_key": false,
    "can_use_custom_api_base": true
  },
  "safety": {
    "read_only": { "editable": false, "value": true },
    "require_approval": { "editable": false, "value": true },
    "max_rows": { "editable": true, "min": 10, "max": 5000, "default": 1000 }
  },
  "preferences": {
    "language": { "options": ["zh-CN", "en", "ja"] },
    "temperature": { "min": 0, "max": 1, "step": 0.1 }
  }
}
```

**PUT /api/user/config**

```json
// Request — 用户保存自己的配置
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o-mini"
  },
  "preferences": {
    "language": "en",
    "temperature": 0.5
  }
}

// Response 200
{
  "merged": {  /* 合并后的完整生效配置 */ },
  "overrides": { /* 用户实际覆盖的部分 */ }
}
```

### 3.3 变更 API 方法

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/config` | **保留**：获取当前生效的运行时配置（合并 admin + user） |
| `POST` | `/api/config` | **废弃**：改为由 `PUT /api/admin/config` 和 `PUT /api/user/config` 替代 |
| `GET` | `/api/admin/config/changelog` | 获取配置变更历史（新增） |
| `GET` | `/api/user/config/history` | 获取用户配置变更历史（新增） |

### 3.4 数据库管理 API（预留）

管理员配置页面中的「数据库管理」Tab 需要有对应的后端 API 支持。现有部分数据库 API 已存在，后续将在独立的设计文档中补充完善：

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| `GET` | `/api/database` | 列出已注册的数据库 | **已有** |
| `POST` | `/api/database/connect` | 注册新的数据库连接 | **已有** |
| `POST` | `/api/database/test` | 测试数据库连接 | **已有** |
| `GET` | `/api/database/{id}/tables` | 获取指定数据库的表结构 | **已有** |
| `PATCH` | `/api/database/{id}` | 更新数据库配置 | **已有** |
| `DELETE` | `/api/database/{id}` | 删除数据库连接 | **已有** |
| `GET` | `/api/admin/databases/health` | 获取所有数据库连接的健康状态 | **待设计** |
| `GET` | `/api/admin/databases/{id}/stats` | 获取单个数据库的使用统计 | **待设计** |

> 注：现有 `/api/database/*` 路由将在后续的数据库管理功能设计中统一整合到管理员配置体系下，并根据角色（admin/user）决定访问权限。

### 3.5 配置合并逻辑

```
用户请求 /api/config 时
  1. 加载 system_config
  2. 加载 user_config（当前登录用户）
  3. 按以下优先级合并：
     - user_config.llm.provider        ← 用户指定，若 admin 允许
     - user_config.llm.model           ← 用户指定，需在 available 范围内
     - user_config.safety.*            ← 用户指定，若 admin 允许且不超限
     - user_config.preferences.*       ← 用户指定，约束范围内
     - 其余字段                        ← system_config 默认值
  4. 返回合并后的配置
```

---

## 4. 前端设计

### 4.1 页面结构概览

```
┌─────────────────────────────────────────────────────────────────┐
│  Data Chat    问你的数据          [⚙️ 系统设置] [👤 用户名 ▼]  │ ← 顶部栏
├──────────────────┬──────────────────────────────────────────────┤
│                  │                                              │
│  📡 LLM 提供商   │  ┌────────────────────────────────────────┐  │
│  🔒 安全设置     │  │  LLM 提供商池                          │  │
│  💾 存储设置     │  │                                        │  │
│  🗄️ 数据库管理   │  │  ☑ OpenAI    模型: gpt-4o, gpt-4o-mini│  │
│  👥 用户管理     │  │  ☑ DeepSeek   模型: deepseek-v4-*     │  │
│  ⚙️ 高级设置     │  │  ☐ Anthropic  (已禁用)                │  │
│  📋 配置日志     │  │  ☑ Ollama     模型: llama3.1, qwen2.5│  │
│                  │  │  [添加自定义提供商]                     │  │
│  ─── 左导航 ───  │  │                                        │  │
│                  │  │  默认模型: [gpt-4o                  ▼] │  │
│                  │  │                                        │  │
│                  │  │  ──── 全局 API Key ────               │  │
│                  │  │  API Key: [••••••••••••••••••••]      │  │
│                  │  │  API Base: [https://api.openai.com/v1] │  │
│                  │  │                                        │  │
│                  │  │              [保存更改]                  │  │
│                  │  └────────────────────────────────────────┘  │
│                  │                                              │
│                  │              ← 右侧工作区 →                  │
├──────────────────┴──────────────────────────────────────────────┤
│  💬 管理员模式  |  LLM 提供商配置   |  变更已保存               │ ← 底部状态栏
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 路由设计

新增两个独立页面（react-router 或条件渲染）：

| 页面 | 路径标识 | 访问权限 |
|------|---------|---------|
| 系统设置（管理员） | `admin/settings` | 仅 `admin` 角色 |
| 个人设置（用户） | `user/settings` | 所有已登录用户 |

**当前前端无 router 库，推荐两种方案**：

**方案 A（推荐）：引入 react-router-dom**
```
/login              → LoginPage
/register           → RegisterPage
/chat               → ChatPage（现有主界面）
/dashboard          → DashboardPage（数据看板）
/admin/settings     → AdminSettingsPage（系统设置，仅 admin）
/user/settings      → UserSettingsPage（个人设置，所有用户）
```

**方案 B（延续现有模式）：Zustand 状态控制**
```
App.tsx
├── showLogin       = true  → LoginPage / RegisterPage
├── showAdminConfig = true  → AdminSettingsPage（覆盖主界面）
├── showUserConfig  = true  → UserSettingsPage（弹窗或覆盖）
├── showDashboard   = true  → DashboardPage
└── default                 → 三栏主界面
```

### 4.3 管理员配置页面 (AdminSettingsPage)

**布局**：左右分栏，左为导航菜单，右为内容区

**左侧导航菜单**：
```
┌──────────────────┐
│  📡 LLM 提供商    │ ← 当前选中
│  🔒 安全设置      │
│  💾 存储设置      │
│  🗄️ 数据库管理    │
│  👥 用户管理      │
│  ⚙️ 高级设置      │
│  📋 配置日志      │
└──────────────────┘
```

**各 Tab 内容**：

#### Tab 1: LLM 提供商

功能：
1. **提供商池管理** — 启用/禁用提供商，配置每个提供商的模型列表
2. **默认模型** — 设置系统默认模型（当用户未选时使用）
3. **全局 API Key** — 为每个提供商配置系统级 API Key
4. **用户权限** — 控制是否允许用户自选 LLM、自填 API Key

UI 设计：
```
┌──────────────────────────────────────────────────────────────┐
│  LLM 提供商池                                                 │
│                                                              │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ ☑ OpenAI          默认: [gpt-4o ▼]                      ││
│  │   模型: [gpt-4o, gpt-4o-mini, gpt-4-turbo, ...]  [编辑] ││
│  │   API Key: [••••••••••••••••]  [测试]                  ││
│  ├──────────────────────────────────────────────────────────┤│
│  │ ☑ DeepSeek       默认: [deepseek-v4-flash ▼]           ││
│  │   模型: [deepseek-v4-flash, deepseek-v4-pro]  [编辑]    ││
│  │   API Key: [••••••••••••••••]  [测试]                  ││
│  ├──────────────────────────────────────────────────────────┤│
│  │ ☐ Anthropic (已禁用)                         [启用]     ││
│  └──────────────────────────────────────────────────────────┘│
│                                                              │
│  [+ 添加自定义提供商]                                         │
│                                                              │
│  ──── 用户 LLM 权限 ────                                     │
│                                                              │
│  [允许用户自选 LLM 提供商]         ● 是  ○ 否                │
│  [允许用户使用自定义 API Key]      ○ 是  ● 否                │
│  [允许用户使用自定义 API Base]     ● 是  ○ 否                │
│                                                              │
│  ┌──────────────────────────────────────────────────────────┐│
│  │  系统默认模型: [gpt-4o                        ▼]        ││
│  └──────────────────────────────────────────────────────────┘│
│                                                              │
│  [保存更改]                                                   │
└──────────────────────────────────────────────────────────────┘
```

#### Tab 2: 安全设置

功能：
1. 系统级安全开关（只读、数据确认、最大行数）
2. 全局屏蔽表和脱敏列
3. 用户覆盖安全设置权限控制

#### Tab 3: 存储设置

功能：
1. 日志存储周期配置
2. 日志保留天数
3. 数据存储位置（只读展示）

#### Tab 4: 数据库管理

**⚠️ 占位 — 待详细设计**

管理员配置页面预留数据库管理入口，后续将在此处设计完整的数据库连接管理功能。初步规划方向包括：

- 查看所有已注册的数据库连接列表
- 新增/编辑/删除数据库连接
- 测试数据库连接连通性
- 配置数据库表过滤规则（包含/排除表）
- 查看数据库 Schema 信息
- 数据库连接池和健康状态监控

> 详细设计参见独立的「数据库管理功能设计文档」（待编写）。

#### Tab 5: 用户管理

功能：
1. 用户列表（表格）：用户名、角色、状态、创建时间、操作
2. 操作为：编辑角色、分配数据库权限、启用/禁用、删除
3. 新增用户（管理员手动创建）
4. 数据库权限分配（复用现有 `DbAccessControl` 弹窗）

UI 设计：
```
┌──────────────────────────────────────────────────────────────┐
│  👥 用户管理                                  [+ 新增用户]  │
│                                                              │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ 用户名      角色    状态    会话数   创建时间      操作   ││
│  ├──────────────────────────────────────────────────────────┤│
│  │ admin     管理员  ● 已启用  12    2025-01-01  [编辑] [权限]││
│  │ alice     用户    ● 已启用   3    2025-05-20  [编辑] [权限]││
│  │ bob       用户    ○ 已禁用   0    2025-05-25  [编辑] [权限]││
│  │ charlie   用户    ● 已启用   1    2025-05-28  [编辑] [权限]││
│  └──────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌─ 编辑用户 ─────────────────────────────────────────────┐  │
│  │  用户名: alice                                         │  │
│  │  角色:   [● 用户  ○ 管理员]                            │  │
│  │  状态:   [● 已启用  ○ 已禁用]                           │  │
│  │                                                         │  │
│  │  [取消]  [保存]                                         │  │
│  └─────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

#### Tab 6: 高级设置

功能：
1. 会话过期时间（分钟）
2. 每用户最大会话数
3. LLM 温度范围限制（最小值、最大值、默认值）

#### Tab 7: 配置日志

功能：
1. 展示系统配置的变更历史
2. 每行显示：变更时间、操作人、变更摘要

### 4.4 用户配置页面 (UserSettingsPage)

**展现形式**：可以是独立页面，也可以是主界面右侧面板的升级版

**布局**：居中卡片式布局，Tab 切换

```
┌──────────────────────────────────────────────────┐
│  个人设置                              [× 关闭]  │
│                                                  │
│  ┌──────────┬────────────────────────────────┐   │
│  │          │                                │   │
│  │  🤖 LLM  │  LLM 提供商: [OpenAI ○]       │   │
│  │   设置   │                                │   │
│  │          │  模型: [gpt-4o          ▼]    │   │
│  │  🔒 安全 │                                │   │
│  │   设置   │  自定义 API Key (可选):         │   │
│  │          │  [••••••••••••••••]           │   │
│  │  🎨 偏好 │                                │   │
│  │   设置   │  API Base (可选):              │   │
│  │          │  [https://api.openai.com/v1]  │   │
│  │          │                                │   │
│  │          │  ──── 说明 ────                │   │
│  │          │  管理员已启用 2 个 LLM 提供商   │   │
│  │          │  自定义 Key 可覆盖全局 Key      │   │
│  │          │                                │   │
│  │          │  [测试连接]  [保存设置]          │   │
│  │          │                                │   │
│  └──────────┴────────────────────────────────┘   │
└──────────────────────────────────────────────────┘
```

**各 Tab 内容**：

#### Tab 1: LLM 设置

| 字段 | 说明 | 来源 |
|------|------|------|
| LLM 提供商 | 从管理员启用的列表中选择 | `GET /api/user/config/available` |
| 模型 | 从该提供商的模型中选择 | 同上 |
| 自定义 API Key | 可选，覆盖全局 Key | 管理员允许时才显示 |
| 自定义 API Base | 可选，覆盖全局 Base | 管理员允许时才显示 |
| 超时时间 | 自定义超时 | 管理员限定的范围内 |

#### Tab 2: 安全设置

| 字段 | 说明 | 可编辑条件 |
|------|------|-----------|
| 只读模式 | 覆盖系统默认 | `admin允许` 且 `allow_user_safety_override = true` |
| 数据确认 | 覆盖系统默认 | 同上 |
| 最大行数 | 覆盖系统默认 | 同上，且不超过 admin 设定的最大值 |

#### Tab 3: 偏好设置

| 字段 | 说明 | 可选值 |
|------|------|--------|
| 界面语言 | 界面显示语言 | 中文 / English / 日本語 |
| 温度 | LLM 创造力 | 管理员设定的范围内滑动 |
| 主题 | 界面风格 | 浅色 / 跟随系统（可选） |
| 默认视图 | 登录后默认页面 | 聊天 / 看板 |
| 会话过期 | 个人会话超时 | 不超过管理员设定值 |

### 4.5 组件树

```
AdminSettingsPage
├── AdminNav                        # 左侧导航菜单
├── LLSettingsTab                   # LLM 提供商配置
│   ├── ProviderCard                # 单个提供商卡片（启用/禁用/模型/Key）
│   ├── AddProviderForm             # 添加自定义提供商表单
│   └── UserLLMPermissions          # 用户 LLM 权限开关
├── SafetySettingsTab               # 安全设置
│   ├── GlobalSafetyToggles         # 全局安全开关组
│   └── BlockedTablesEditor         # 屏蔽表/脱敏列编辑器
├── StorageSettingsTab              # 存储设置
│   └── StorageConfigForm           # 存储配置表单
├── DatabaseManagementTab           # 数据库管理（预留，待详细设计）
│   └── (占位 — 后续实现)
├── UserManagementTab               # 用户管理
│   ├── UserTable                   # 用户列表表格
│   ├── UserEditModal               # 编辑用户弹窗
│   └── DbAccessControl             # 数据库权限分配（复用现有）
├── AdvancedSettingsTab             # 高级设置
│   └── AdvancedConfigForm          # 高级配置表单
└── ConfigLogTab                    # 配置变更日志
    └── ChangeLogTable              # 变更历史表格

UserSettingsPage
├── UserLLMSettingsTab              # 个人 LLM 设置
│   ├── ProviderSelector            # 提供商选择器
│   ├── ModelSelector               # 模型选择器
│   └── APIKeyInput                 # 自定义 Key 输入（条件显示）
├── UserSafetySettingsTab           # 个人安全设置
│   └── SafetyOverrideControls      # 安全设置覆盖控件
└── UserPreferencesTab              # 个人偏好
    ├── LanguageSelector            # 语言选择
    ├── TemperatureSlider           # 温度滑动条
    ├── ThemeSelector               # 主题选择
    └── DefaultViewSelector         # 默认视图选择
```

### 4.6 状态管理扩展

在 Zustand store 中新增：

```typescript
interface AppState {
  // ... 现有状态

  // 配置页面 UI 状态
  showAdminSettings: boolean        // 是否显示管理员设置页
  showUserSettings: boolean         // 是否显示用户设置页
  activeAdminTab: string            // 管理员设置当前 Tab
  activeUserTab: string             // 用户设置当前 Tab

  // 系统配置（管理员）
  systemConfig: SystemConfig | null

  // 用户可用选项
  userAvailableOptions: UserAvailableOptions | null

  // Actions
  setShowAdminSettings: (show: boolean) => void
  setShowUserSettings: (show: boolean) => void
  setActiveAdminTab: (tab: string) => void
  setActiveUserTab: (tab: string) => void
  setSystemConfig: (config: SystemConfig) => void
  setUserAvailableOptions: (options: UserAvailableOptions) => void
}
```

### 4.7 API Client 扩展

```typescript
// api/index.ts 新增

// ===== 管理员配置 API =====
getSystemConfig(): Promise<SystemConfig>
updateSystemConfig(config: Partial<SystemConfig>): Promise<SystemConfig>
getConfigChangelog(): Promise<ChangeLogEntry[]>

// ===== 用户配置 API =====
getUserConfig(): Promise<UserConfig>
updateUserConfig(config: Partial<UserConfig>): Promise<{ merged: UserConfig; overrides: Partial<UserConfig> }>
getUserAvailableOptions(): Promise<UserAvailableOptions>
getUserConfigHistory(): Promise<ChangeLogEntry[]>
```

### 4.8 现有 ConfigPanel 的演进

`ConfigPanel` 组件需要根据用户角色决定显示内容：

```
ConfigPanel (右侧面板)
├── 用户已登录 + 角色为 user → 显示「个人设置」精简版
│   （仅显示 LLM 选择、个人偏好，不显示系统级设置）
├── 用户已登录 + 角色为 admin → 显示「个人设置」+「进入系统设置」入口
│   （点击后跳转到 AdminSettingsPage）
└── 未登录（单用户模式）→ 显示完整配置（兼容现有行为）
```

---

## 5. 数据库迁移

### 5.1 新增表

```sql
-- 系统配置表（单行）
CREATE TABLE IF NOT EXISTS system_config (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    config      TEXT NOT NULL DEFAULT '{}',
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by  TEXT REFERENCES users(id)
);

-- 用户配置表
CREATE TABLE IF NOT EXISTS user_configs (
    user_id     TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    config      TEXT NOT NULL DEFAULT '{}',
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 配置变更日志
CREATE TABLE IF NOT EXISTS config_changelog (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    config_type TEXT NOT NULL CHECK (config_type IN ('system', 'user')),
    user_id     TEXT REFERENCES users(id),
    changed_by  TEXT NOT NULL,                     -- 操作人 username
    summary     TEXT NOT NULL,                     -- 变更摘要（如 "修改 LLM 默认模型"）
    diff        TEXT,                              -- JSON diff（可选，记录详细变更）
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### 5.2 数据迁移

新建 `backend/app/persistence/migration_003_configs.py`：

```python
def migrate_configs(conn: sqlite3.Connection):
    """配置分层管理的数据库迁移。"""
    cursor = conn.cursor()

    # 创建 system_config 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_config (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            config      TEXT NOT NULL DEFAULT '{}',
            updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_by  TEXT REFERENCES users(id)
        )
    ''')

    # 创建 user_configs 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_configs (
            user_id     TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            config      TEXT NOT NULL DEFAULT '{}',
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    ''')

    # 创建 config_changelog 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config_changelog (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            config_type TEXT NOT NULL CHECK (config_type IN ('system', 'user')),
            user_id     TEXT REFERENCES users(id),
            changed_by  TEXT NOT NULL,
            summary     TEXT NOT NULL,
            diff        TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    ''')

    # 迁移现有 config 表数据到 system_config
    existing = cursor.execute('SELECT COUNT(*) FROM system_config').fetchone()[0]
    if existing == 0:
        # 尝试从旧的 config 表读取
        old_config = cursor.execute('SELECT value FROM config WHERE key = ?', ('config',)).fetchone()
        initial_config = {}

        if old_config:
            try:
                import json
                old_data = json.loads(old_config[0])
                # 映射旧字段到新结构
                safety = old_data.get('safety', {})
                initial_config = {
                    'llm': {
                        'provider_pool': [
                            {'provider': 'openai', 'label': 'OpenAI', 'models': ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'], 'enabled': True},
                            {'provider': 'deepseek', 'label': 'DeepSeek', 'models': ['deepseek-v4-flash', 'deepseek-v4-pro'], 'enabled': True},
                            {'provider': 'azure', 'label': 'Azure OpenAI', 'models': ['gpt-4o', 'gpt-4', 'gpt-35-turbo'], 'enabled': False},
                            {'provider': 'anthropic', 'label': 'Anthropic', 'models': ['claude-3-5-sonnet', 'claude-3-haiku'], 'enabled': False},
                            {'provider': 'ollama', 'label': 'Ollama', 'models': ['llama3.1', 'qwen2.5', 'mistral'], 'enabled': True},
                        ],
                        'default_model': old_data.get('llm', {}).get('model', 'gpt-4o'),
                    },
                    'safety': {
                        'read_only': safety.get('read_only', True),
                        'require_approval': safety.get('require_approval', True),
                        'max_rows': safety.get('max_rows', 1000),
                        'blocked_tables': safety.get('restricted_tables', []),
                        'masked_columns': safety.get('masked_columns', []),
                    },
                    'advanced': {
                        'session_expire_minutes': 1440,
                        'max_sessions_per_user': 50,
                        'allow_user_llm_config': True,
                        'allow_user_safety_override': False,
                        'llm_temperature_range': {'min': 0, 'max': 1, 'default': 0.3},
                    },
                    'storage': {
                        'log_interval': old_data.get('storage', {}).get('log_interval', 'day'),
                        'log_retention_days': old_data.get('storage', {}).get('log_retention_days', 30),
                    },
                }
            except (json.JSONDecodeError, AttributeError):
                pass

        cursor.execute(
            'INSERT INTO system_config (id, config, updated_at) VALUES (1, ?, datetime("now"))',
            (json.dumps(initial_config),)
        )

    conn.commit()
```

---

## 6. UI 交互设计

### 6.1 管理员配置入口

在顶部栏右侧增加两个入口：

```
┌──────────────────────────────────────────────────────────────┐
│  Data Chat    问你的数据          [👥 用户管理] [⚙️ 系统设置]  │
└──────────────────────────────────────────────────────────────┘
```

- `⚙️ 系统设置`：仅管理员可见，点击进入 `AdminSettingsPage`
- `👥 用户管理`：仅管理员可见，点击快速跳转到用户管理 Tab（也可作为系统设置的一个子 Tab）

### 6.2 用户配置入口

用户在顶部栏的个人菜单中：

```
┌──────────────────────────────────────────────────────────────┐
│  Data Chat    问你的数据          [🔔] [👤 用户名 ▼]         │
└──────────────────────────────────────────────────────────────┘
                                          │
                                    ┌─────┴──────┐
                                    │  个人设置    │
                                    │  退出登录    │
                                    └────────────┘
```

### 6.3 保存与反馈

| 操作 | 反馈 |
|------|------|
| 保存系统配置 | Toast: "✅ 系统配置已保存"；若影响运行时，提示 "部分配置需重启生效" |
| 保存用户配置 | Toast: "✅ 个人设置已保存"，配置立即生效 |
| 配置校验失败 | Toast: "❌ {错误原因}"，表单高亮错误字段 |
| 测试 LLM 连接 | 内联显示结果: "✅ 连接成功 (158ms)" 或 "❌ 连接失败: {原因}" |

---

## 7. 实施步骤

### Phase 1: 后端数据层
1. 新增配置数据模型 `system_config`、`user_configs`、`config_changelog` 表
2. 创建迁移脚本 `migration_003_configs.py`
3. 实现配置存储服务（读写 JSON、合并逻辑）

### Phase 2: 后端 API
1. 实现 `/api/admin/config` 路由（GET / PUT / PATCH）
2. 实现 `/api/user/config` 路由（GET / PUT）
3. 实现 `/api/user/config/available` 路由
4. 实现配置变更日志记录
5. 保留并适配 `/api/config` 向后兼容

### Phase 3: 前端管理员页面
1. 创建 `AdminSettingsPage` 及子组件
2. 创建左侧导航菜单组件 `AdminNav`
3. 实现各 Tab 内容组件（LLM / 安全 / 存储 / 数据库管理 / 用户管理 / 高级 / 日志）
4. 「数据库管理」Tab 先放置占位内容，待后续详细设计后实现
5. 集成 API，实现配置的加载与保存
6. 顶部栏添加管理员入口

### Phase 4: 前端用户设置
1. 创建 `UserSettingsPage` 及子组件
2. 实现进阶 ConfigPanel 的按角色显示逻辑
3. 集成 `GET /api/user/config/available` 实现选项约束
4. 顶部栏添加用户个人菜单入口

### Phase 5: 集成与测试
1. 多用户场景下配置隔离验证
2. 权限边界测试（普通用户不可访问 admin API）
3. 配置合并逻辑单元测试
4. 向后兼容测试（无 auth 单用户模式）

---

## 8. 影响范围分析

| 模块 | 改动量 | 风险 | 兼容性 |
|------|--------|------|--------|
| 数据库 | 新增 3 张表，旧 `config` 表数据迁移 | 低 | 向后兼容 |
| 后端路由 | 新增 6+ 个端点，保留旧 `/api/config` | 低 | 完全兼容 |
| 后端配置服务 | 新增配置合并逻辑 | 中 | — |
| 前端状态管理 | 新增 systemConfig / UI 状态 | 低 | — |
| 前端组件 | 新增 20+ 组件，修改 ConfigPanel / App / Sidebar | 中 | 旧面板保留 |
| 前端 API 层 | 新增 ~10 个方法 | 低 | — |
| 现有功能 | `ConfigPanel` 行为不变，新增页面不干扰主流程 | 低 | 完全向后兼容 |
