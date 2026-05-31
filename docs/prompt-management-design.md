# Prompt 管理功能 — 设计方案

## 目标

在系统管理页面新增一个 "Prompt 管理" Tab，让管理员可以可视化管理所有 Agent 用到的 Prompt（支持版本化、存储于 SQLite 数据库）。

---

## 一、Prompt 清单

经过全量代码审查，共 **6 个**需要管理的 Prompt，按 Agent 分为 3 大类：

### 1. 数据分析 Agent（SimpleAgent，所有模式共用）

| 数据库 `name` | 显示名 | 后端位置 | 现状 |
|--------------|--------|---------|------|
| `system` | 系统提示词 | [main.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/main.py#L128-L158) 从 DB 加载 → 传给 Agent | DB 中存为 `name='default'`，需迁移 |
| `sql_gen` | SQL 生成提示词 | [sql_tool.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/agent/tools/sql_tool.py#L27-L39) | 硬编码内联 |

### 2. 深度分析 Agent（AdvancedAgent，质量模式专属）

| 数据库 `name` | 显示名 | 后端位置 | 现状 |
|--------------|--------|---------|------|
| `plan` | 规划提示词 | [advanced_agent.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/agent/advanced_agent.py#L23-L49) | 硬编码常量 `PLAN_PROMPT` |
| `plan_reflect` | 规划审核提示词 | [advanced_agent.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/agent/advanced_agent.py#L51-L67) | 硬编码常量 `PLAN_REFLECT_PROMPT` |
| `report_reflect` | 报告审核提示词 | [advanced_agent.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/agent/advanced_agent.py#L69-L85) | 硬编码常量 `REPORT_REFLECT_PROMPT` |

### 3. Schema 描述 Agent（DescribeSchemaAgent）

| 数据库 `name` | 显示名 | 后端位置 | 现状 |
|--------------|--------|---------|------|
| `schema_describe` | 描述生成提示词 | [describe_schema_agent.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/agent/describe_schema_agent.py#L24-L48) | 硬编码常量 `SYSTEM_PROMPT` |

### 不纳入管理的内部 Prompt

| Prompt | 位置 | 原因 |
|--------|------|------|
| 对话压缩提示词 | [simple_agent.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/agent/simple_agent.py#L146-L147) | 内部实现细节 |
| 报告撰写提示词 | [advanced_agent.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/agent/advanced_agent.py#L581-L587) | 内部实现细节 |
| 补充查询提示词 | [advanced_agent.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/agent/advanced_agent.py#L683-L688) | 内部实现细节 |
| 报告重生成提示词 | [advanced_agent.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/agent/advanced_agent.py#L720-L724) | 内部实现细节 |

---

## 二、数据库设计

直接复用现有 `prompts` 表，**无需 DDL 变更**：

```sql
CREATE TABLE IF NOT EXISTS prompts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,        -- 分类名: system | sql_gen | plan | plan_reflect | report_reflect | schema_describe
    content    TEXT NOT NULL,        -- Prompt 内容
    version    INTEGER NOT NULL DEFAULT 1,
    is_active  INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL
);
```

### 迁移

- 将现有 `name='default'` 的记录改为 `name='system'`（保持原有 content 和 version 不变）
- 在 seed 数据中为其余 5 个分类插入默认 prompt（仅当该分类无记录时）

---

## 三、后端 API 设计

### 现有 API（微调）

| 方法 | 端点 | 变更 |
|------|------|------|
| `GET` | `/api/prompts?category=system` | 增加可选的 `category` 查询参数过滤 |
| `GET` | `/api/prompts/{id}` | 不变 |
| `PUT` | `/api/prompts` | 请求体 `name` 改用 `category` 语义 |

### 新增 API

| 方法 | 端点 | 说明 |
|------|------|------|
| `PATCH` | `/api/prompts/{id}/activate` | 激活指定版本，自动停用同分类其他版本 |
| `GET` | `/api/prompts/active` | 获取所有分类的当前激活版本（含 fallback） |
| `GET` | `/api/prompts/{category}/default` | 获取某分类的硬编码默认 prompt 内容 |

### 核心数据流

```
启动时 main.py
    │
    ├── 调用 GET /api/prompts/active 获取所有分类的 active prompt
    │       │
    │       ├── system        → SimpleAgent.system_prompt
    │       ├── sql_gen       → sql_tool.handle_sql_query()
    │       ├── plan          → AdvancedAgent (构造函数参数)
    │       ├── plan_reflect  → AdvancedAgent (构造函数参数)
    │       ├── report_reflect→ AdvancedAgent (构造函数参数)
    │       └── schema_describe → DescribeSchemaAgent (构造函数参数)
    │
    └── 如果某分类无 active 记录 → 使用硬编码 default 作为 fallback
```

---

## 四、前端设计

### 4.1 新增类型

```typescript
interface PromptInfo {
  id: number
  name: string        // 分类标识
  content: string
  version: number
  is_active: boolean
  created_at: number
}

interface PromptListResponse {
  prompts: PromptInfo[]
}

interface ActivePromptsResponse {
  [category: string]: PromptInfo | null
}
```

### 4.2 新增 API 方法

```typescript
api.getPrompts(category?: string)    // → PromptListResponse
api.getPrompt(id: number)            // → PromptInfo
api.upsertPrompt(category: string, content: string, name?: string)  // → { ok, version }
api.activatePrompt(id: number)       // → { ok }
api.getActivePrompts()               // → ActivePromptsResponse
api.getDefaultPrompt(category: string) // → { content: string }
```

### 4.3 UI 布局

```
┌─────────────────────────────────────────────────────────┐
│  Prompt 管理                                             │
│                                                          │
│  ┌─ 数据分析 Agent（所有模式共用）─────────────────────┐ │
│  │ ├─ 系统提示词        v3 ✓    [编辑] [查看历史]      │ │
│  │ └─ SQL 生成提示词     v2 ✓    [编辑] [查看历史]      │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─ 深度分析 Agent（质量模式）──────────────────────────┐ │
│  │ ├─ 规划提示词        v1 ✓    [编辑] [查看历史]      │ │
│  │ ├─ 规划审核提示词     v1 ✓    [编辑] [查看历史]      │ │
│  │ └─ 报告审核提示词     v1 ✓    [编辑] [查看历史]      │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─ Schema 描述 Agent──────────────────────────────────┐ │
│  │ └─ 描述生成提示词     v1 ✓    [编辑] [查看历史]      │ │
│  └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 4.4 编辑对话框

点击 [编辑] → 弹出模态框：

```
┌── 编辑 Prompt ───────────────────────────────────┐
│  分类: 数据分析 Agent · 系统提示词               │
│  当前版本: v3 · 2026-05-30 15:30                 │
│                                                   │
│  ┌───────────────────────────────────────────┐    │
│  │ <instructions>                             │    │
│  │   <role>data-analyst</role>                │    │
│  │   ...                                      │    │
│  │ </instructions>                            │    │
│  └───────────────────────────────────────────┘    │
│                                                   │
│  [恢复默认]      [保存为新版本 v4]      [取消]    │
│                                                   │
│  ── 版本历史 ──                                   │
│  v3 (当前)  2026-05-30  [设为当前版本]            │
│  v2         2026-05-25  [设为当前版本]            │
│  v1         2026-05-20  [设为当前版本]            │
└───────────────────────────────────────────────────┘
```

---

## 五、实施路线

### Phase 1: 后端 API 扩展（3 个文件）

| 步骤 | 文件 | 具体内容 |
|------|------|---------|
| 1a | [persistence/__init__.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/persistence/__init__.py) | 添加 `_migrate_prompt_name()` 将 `default` → `system`；扩展 seed 数据 |
| 1b | [routes/config.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/routes/config.py) | 改造现有 API + 新增 3 个端点 |
| 1c | `backend/tests/test_prompt_api.py` | API 测试覆盖 |

### Phase 2: Agent 解耦硬编码（5 个文件）

| 步骤 | 文件 | 具体内容 |
|------|------|---------|
| 2a | [sql_tool.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/agent/tools/sql_tool.py) | `handle_sql_query()` 新增 `sql_gen_prompt` 参数 |
| 2b | [advanced_agent.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/agent/advanced_agent.py) | 构造函数新增 3 个 prompt 参数，移除硬编码常量 |
| 2c | [describe_schema_agent.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/agent/describe_schema_agent.py) | 构造函数新增 `system_prompt` 参数，移除硬编码 |
| 2d | [main.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/main.py) | 启动时加载所有 6 个分类的 prompt，注入 Agent |
| 2e | 更新已有测试 | `test_advanced_agent.py` 等适配新构造函数 |

### Phase 3: 前端 UI（4 个文件）

| 步骤 | 文件 | 具体内容 |
|------|------|---------|
| 3a | [types/index.ts](file:///Users/chendong/Projects/agentic-data-analyst/frontend/src/types/index.ts) | 新增 prompt 相关类型 |
| 3b | [api/index.ts](file:///Users/chendong/Projects/agentic-data-analyst/frontend/src/api/index.ts) | 新增 6 个 API 方法 |
| 3c | [PromptManagementTab.tsx](file:///Users/chendong/Projects/agentic-data-analyst/frontend/src/pages/AdminSettings/tabs/PromptManagementTab.tsx) | 新建组件 |
| 3d | [AdminSettingsPage.tsx](file:///Users/chendong/Projects/agentic-data-analyst/frontend/src/pages/AdminSettingsPage.tsx) | 注册 Tab |
| 3e | 前端测试 | `PromptManagementTab.test.tsx` |
