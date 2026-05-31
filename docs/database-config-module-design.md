# 数据库配置模块设计文档

## 1. 概述

### 1.1 需求总览

管理员需要一个完整的数据库配置管理模块，核心流程如下：

```
添加数据库（连接字符串） → 测试连通性 → 导入 Schema → Agent 生成 Description → 人工编辑 → 用于 SQL 分析
```

### 1.2 核心概念

| 概念 | 说明 |
|------|------|
| **Database** | 数据库连接，包含连接字符串、类型等信息 |
| **Table** | 数据库中的表，从远程数据库导入到本地元数据 |
| **Column** | 表中的列，从远程数据库导入 |
| **Description** | 表/列的语义描述，由 Agent 生成后人工校验编辑 |
| **Schema** | 完整的表结构 + 描述，最终用于 Agent 的 SQL 生成 |

---

## 2. 数据模型设计

### 2.1 SQLite 新增表

在现有的 `databases` 表基础上，新增三张表：`imported_tables`、`imported_columns`、`column_descriptions`。

#### 2.1.1 databases 表（已有，增加字段）

现有 `databases` 表结构已经基本满足需求，只需增加一个 `sync_status` 字段：

```sql
-- 新增字段: schema 导入状态
ALTER TABLE databases ADD COLUMN schema_status TEXT DEFAULT 'pending';
-- 可选值: pending, importing, imported, error
-- pending   = 刚添加，未导入 schema
-- importing = 正在导入 schema
-- imported  = schema 已导入
-- error     = 导入失败
```

#### 2.1.2 imported_tables（新增）

```sql
CREATE TABLE IF NOT EXISTS imported_tables (
    id              TEXT PRIMARY KEY,
    database_id     TEXT NOT NULL REFERENCES databases(id) ON DELETE CASCADE,
    table_name      TEXT NOT NULL,
    table_type      TEXT DEFAULT 'TABLE',   -- TABLE / VIEW
    row_count       INTEGER,                -- 导入时的行数估计
    description     TEXT DEFAULT '',         -- Agent 生成的描述
    description_en  TEXT DEFAULT '',         -- 英文描述（可选）
    raw_ddl         TEXT,                    -- 建表语句（可选，供参考）
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL
);
CREATE UNIQUE INDEX idx_imported_tables_db_table ON imported_tables(database_id, table_name);
```

#### 2.1.3 imported_columns（新增）

```sql
CREATE TABLE IF NOT EXISTS imported_columns (
    id              TEXT PRIMARY KEY,
    table_id        TEXT NOT NULL REFERENCES imported_tables(id) ON DELETE CASCADE,
    column_name     TEXT NOT NULL,
    data_type       TEXT NOT NULL,
    is_nullable     INTEGER DEFAULT 1,
    is_primary_key  INTEGER DEFAULT 0,
    default_value   TEXT,
    ordinal_position INTEGER,
    description     TEXT DEFAULT '',         -- Agent 生成的描述
    sample_values   TEXT,                    -- 示例值 (JSON array, 供 Agent 参考)
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL
);
CREATE INDEX idx_imported_columns_table ON imported_columns(table_id);
```

> **设计说明**：将 `description` 直接放在 `imported_tables` 和 `imported_columns` 表上，而不是单独一张描述表。原因：
> 1. description 是表和列的一个属性，1:1 关系，不需要多态关联
> 2. 查询时不需要 JOIN，性能更好
> 3. 更新描述就是简单的 UPDATE 操作

### 2.2 Pydantic 模型

在 `backend/app/models/database.py` 中新增：

```python
class TableSchema(BaseModel):
    """从远程数据库导入的表结构"""
    table_name: str
    table_type: str = "TABLE"
    columns: list[ColumnSchema]

class ColumnSchema(BaseModel):
    """从远程数据库导入的列结构"""
    column_name: str
    data_type: str
    is_nullable: bool = True
    is_primary_key: bool = False
    default_value: str | None = None
    ordinal_position: int = 0

class ImportedTableInfo(BaseModel):
    """已导入的表 + 描述"""
    id: str
    database_id: str
    table_name: str
    table_type: str
    description: str = ""
    row_count: int | None = None
    columns: list[ImportedColumnInfo]
    created_at: float
    updated_at: float

class ImportedColumnInfo(BaseModel):
    """已导入的列 + 描述"""
    id: str
    column_name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool
    description: str = ""
    sample_values: list[str] | None = None

class SchemaImportRequest(BaseModel):
    """导入 schema 请求"""
    database_id: str
    include_tables: list[str] | None = None  # 留空 = 全部导入
    exclude_tables: list[str] | None = None

class DescriptionGenerateRequest(BaseModel):
    """生成/更新描述请求"""
    database_id: str
    table_ids: list[str] | None = None  # 留空 = 所有未生成的表
    language: str = "zh"  # zh / en

class DescriptionUpdateRequest(BaseModel):
    """人工更新描述"""
    table_id: str | None = None
    column_id: str | None = None
    description: str
```

---

## 3. 后端 API 设计

### 3.1 新增 API 端点

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/database/{db_id}/schema/import` | 导入数据库 Schema 到本地 |
| GET | `/api/database/{db_id}/schema` | 获取已导入的 Schema（含描述） |
| GET | `/api/database/{db_id}/schema/status` | 获取 Schema 导入状态 |
| POST | `/api/database/{db_id}/schema/describe` | Agent 生成 Schema 描述 |
| PATCH | `/api/database/{db_id}/schema/describe` | 人工更新表/列的描述 |

### 3.2 详细 API 设计

#### POST `/api/database/{db_id}/schema/import`

导入数据库 Schema：

```python
async def import_schema(db_id: str, req: SchemaImportRequest):
    """
    1. 根据 db_id 找到数据库连接配置
    2. 连接到远程数据库
    3. 读取 information_schema 获取所有表/列
    4. 按 include_tables / exclude_tables 过滤
    5. 写入 imported_tables / imported_columns 表
    6. 更新 databases.schema_status = 'imported'
    7. 返回导入的统计信息
    """
    # 返回: {"ok": true, "tables_count": 15, "columns_count": 120}
```

#### POST `/api/database/{db_id}/schema/describe`

Agent 生成描述：

```python
async def describe_schema(db_id: str, req: DescriptionGenerateRequest):
    """
    1. 从 imported_tables / imported_columns 读取未描述的表和列
    2. 对每个表，收集其列名、类型、示例值等信息
    3. 调用 LLM Agent 生成中文语义描述
    4. 存量描述到 imported_tables.description / imported_columns.description
    5. 返回生成的描述统计
    """
    # 调用 describe_schema_agent.generate_descriptions(tables_info)
    # 返回: {"ok": true, "tables_described": 15, "columns_described": 120}
```

#### PATCH `/api/database/{db_id}/schema/describe`

人工编辑描述：

```python
async def update_description(db_id: str, req: DescriptionUpdateRequest):
    """
    1. 校验 table_id 或 column_id 属于该 database
    2. 更新对应记录的 description 字段
    3. 记录 updated_at 时间戳
    """
    # 返回: {"ok": true}
```

### 3.3 现有 API 的修改

#### GET `/api/database/{db_id}/tables`（已有）

修改此端点，使其返回的描述信息包含已导入的 description 字段。

或者保持原端点不变（用于实时浏览），新增 `/api/database/{db_id}/schema` 端点用于获取带描述的本地 Schema。

建议：保持 `GET /api/database/{db_id}/tables` 不变（用于实时浏览远程库），新增 `GET /api/database/{db_id}/schema`（返回本地已导入的带描述的结构）。

---

## 4. Agent 设计：Schema Description Agent

### 4.1 架构位置

新建文件 `backend/app/agent/describe_schema_agent.py`，与现有的 `simple_agent.py`、`advanced_agent.py` 同级。

不通过 Tool Registry 注册，而是作为一个独立服务函数被路由层直接调用。

### 4.2 核心逻辑

```
输入: 表名 + 列信息列表 (列名, 类型, 是否主键, 示例值)
输出: {表描述, 列描述列表}

处理流程:
1. 收集一个数据库中所有待处理的表和列信息
2. 构造 prompt，分批发送给 LLM（每批最多 8 张表，避免超出 token 限制）
3. 解析 LLM 返回的结构化 JSON
4. 存量到数据库
```

### 4.3 Prompt 设计

```python
SYSTEM_PROMPT = """你是一个数据分析专家，负责为数据库表和字段添加中文语义描述。
你的描述能让数据分析师快速理解每个表和字段的业务含义。

## 输出要求
返回 JSON 数组，每个元素包含：
- table_name: 表名
- table_description: 表的中文业务描述（20-50字）
- columns: 列描述数组
  - column_name: 列名
  - column_description: 列的中文业务描述（10-30字）

## 描述规范
1. 描述要有实际业务含义，不要只是直译英文名
2. 如果字段有外键关系（如 customer_id），要说明指向哪个表
3. 主键字段要标注
4. 时间字段要说明格式和时区（如已知）
5. 金额字段要说明币种
"""

USER_PROMPT_TEMPLATE = """请为以下数据库表和字段添加中文描述：

数据库名称: {database_name}

{ tables_info }

请分析表名和字段名，给出合理的中文业务描述。"""
```

### 4.4 分片策略

```python
async def generate_descriptions(database_id: str, table_ids: list[str] | None = None):
    """为指定数据库的表生成描述"""

    # 1. 获取所有待处理的表
    tables = get_tables_for_describe(database_id, table_ids)

    # 2. 每 8 张表为一个 batch
    BATCH_SIZE = 8
    all_results = []

    for i in range(0, len(tables), BATCH_SIZE):
        batch = tables[i:i + BATCH_SIZE]

        # 构造 prompt
        prompt = build_description_prompt(batch)

        # 调用 LLM
        response = await call_llm([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ], response_format={"type": "json_object"})

        # 解析结果
        parsed = parse_llm_response(response)
        all_results.extend(parsed)

    # 3. 存量到数据库
    save_descriptions(database_id, all_results)

    return all_results
```

### 4.5 增量更新

- Agent 只处理 `description` 为空的表和列（不覆盖人工编辑的内容）
- 提供"强制重新生成"选项，覆盖所有描述
- 人工编辑后标记 `updated_at`，Agent 可以识别哪些是人工编辑过的

---

## 5. 前端设计

### 5.1 新增页面

**数据库管理页面（DatabaseManagerPage）** — 独立的、仅管理员可访问的页面。

#### 入口

在 Sidebar 底部增加"数据库管理"按钮，点击后跳转到数据库管理页面。

```
[数据库列表区域]
  数据库1
  数据库2
  ...
  ─────────────
  + 添加数据库      ← 现有按钮，打开 DBConnectModal
  ⚙ 数据库管理      ← 新增按钮，打开独立管理页面
```

#### 页面布局

```
┌─────────────────────────────────────────────────────┐
│  数据库管理                                    [返回] │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────┐  ┌──────────────────────────────┐ │
│  │  数据库列表   │  │  内容区域                    │ │
│  │             │  │                              │ │
│  │  📦 零售库   │  │  [Schema 导入面板]           │ │
│  │  📦 财务库   │  │  [Table 列表 + 描述编辑]     │ │
│  │  📦 日志库   │  │  [Column 详情 + 描述编辑]    │ │
│  │             │  │                              │ │
│  │  + 新建     │  │                              │ │
│  └─────────────┘  └──────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### 5.2 组件树

```
DatabaseManagerPage
├── DbListPanel (左侧列表)
│   ├── DbListItem (数据库条目)
│   │   ├── 名称、类型图标、连接状态
│   │   └── schema_status 状态标签 (pending/importing/imported/error)
│   └── AddDbButton (添加数据库 / 打开 DBConnectModal)
│
├── SchemaPanel (右侧内容区 - 按选定数据库展示)
│   ├── SchemaImportBar (导入操作栏)
│   │   ├── 显示当前 schema_status
│   │   ├── "导入 Schema" 按钮
│   │   ├── "生成描述" 按钮 (Agent)
│   │   └── 进度条 / 状态指示
│   │
│   ├── TableList (表列表)
│   │   └── TableCard (单个表卡片)
│   │       ├── 表名、类型 (TABLE/VIEW)
│   │       ├── 行数估计
│   │       ├── DescriptionEditor (描述编辑区 - 可内联编辑)
│   │       └── ColumnList (列列表)
│   │           └── ColumnRow (单列)
│   │               ├── 列名、类型、主键标识
│   │               └── DescriptionEditor (列描述编辑区)
│   │
│   ├── FilterBar (筛选栏)
│   │   ├── 搜索框 (按表名/描述筛选)
│   │   └── 状态筛选 (全部/已描述/未描述)
│   │
│   └── EmptyState (未选择数据库时的提示)
```

### 5.3 关键交互流程

#### 流程 1：添加数据库

```
Sidebar "添加数据库" 按钮 → DBConnectModal 打开
  → 填写信息 → "测试连接" → 显示结果
  → "保存并连接" → 关闭弹窗 → 刷新列表
```

#### 流程 2：导入 Schema

```
管理员点击某数据库 → 右侧显示详情
  → schema_status 为 "pending"
  → 点击 "导入 Schema" 按钮
  → 后端连接远程数据库，读取 information_schema
  → 前端显示导入进度 (loading 状态)
  → 完成后表结构展现在右侧
```

#### 流程 3：Agent 生成描述

```
Schema 导入完成后
  → 所有 description 字段为空
  → 点击 "生成描述" 按钮
  → 调用 POST /api/database/{id}/schema/describe
  → 前端轮询进度 (或等待完成)
  → 完成后每个表/列的描述自动填充
```

#### 流程 4：人工编辑描述

```
在任何 TableCard 或 ColumnRow 上
  → 点击描述文本区域 → 进入编辑模式
  → 修改描述内容
  → 失去焦点或按 Enter → 自动保存
  → 显示 "已保存" 提示
```

### 5.4 前端类型定义新增

在 `frontend/src/types/index.ts` 中新增：

```typescript
// ===== Schema 管理 =====
export interface ImportedTable {
  id: string
  database_id: string
  table_name: string
  table_type: string
  description: string
  row_count?: number
  columns: ImportedColumn[]
  created_at: number
  updated_at: number
}

export interface ImportedColumn {
  id: string
  column_name: string
  data_type: string
  is_nullable: boolean
  is_primary_key: boolean
  description: string
  sample_values?: string[]
}

export interface SchemaStatus {
  schema_status: 'pending' | 'importing' | 'imported' | 'error'
  tables_count: number
  columns_count: number
  described_tables: number
  described_columns: number
}

export interface DescriptionGenerateRequest {
  table_ids?: string[]
  language?: string
}

export interface DescriptionUpdateRequest {
  table_id?: string
  column_id?: string
  description: string
}
```

### 5.5 API 客户端新增

在 `frontend/src/api/index.ts` 中新增：

```typescript
// ===== Schema 管理 =====
importSchema(dbId: string, data?: { include_tables?: string[]; exclude_tables?: string[] }): Promise<{ ok: boolean; tables_count: number; columns_count: number }> {
  return request(`/database/${dbId}/schema/import`, {
    method: 'POST',
    body: JSON.stringify(data || {}),
  })
},

getImportedSchema(dbId: string): Promise<{ tables: ImportedTable[] }> {
  return request(`/database/${dbId}/schema`)
},

getSchemaStatus(dbId: string): Promise<SchemaStatus> {
  return request(`/database/${dbId}/schema/status`)
},

generateDescriptions(dbId: string, data?: DescriptionGenerateRequest): Promise<{ ok: boolean; tables_described: number; columns_described: number }> {
  return request(`/database/${dbId}/schema/describe`, {
    method: 'POST',
    body: JSON.stringify(data || {}),
  })
},

updateDescription(dbId: string, data: DescriptionUpdateRequest): Promise<{ ok: boolean }> {
  return request(`/database/${dbId}/schema/describe`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
},
```

---

## 6. Schema 描述在 SQL 分析中的应用

### 6.1 现有 Schema Prompt 的改造

当前 [schema.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/db/schema.py) 中的 `build_schema_prompt` 使用硬编码的描述字典：

```python
# 当前做法（硬编码）
descriptions = {
    "dim_customer": "客户信息（含 full_name 姓名）",
    "dim_product": "产品信息（名称、类别）",
    # ...
}
```

改造后，从 `imported_tables` 和 `imported_columns` 中读取动态描述：

```python
# 改造后（动态读取）
def build_schema_prompt(tables, db_id: str | None = None) -> str:
    """Full schema with dynamic descriptions."""
    # 读取本地存储的描述
    descriptions = get_descriptions(db_id) if db_id else {}
    lines = ["以下是数据库中的表和字段：\n"]
    for t in tables:
        table_desc = descriptions.get(t.name, {}).get("description", "")
        lines.append(t.to_prompt_block(table_desc=table_desc))
    return "\n".join(lines)
```

### 6.2 预期效果

- 管理员为零售库添加描述后，Analyst Agent 能理解 `fct_orders` 是"订单头表，包含订单日期、客户 ID、总金额等汇总信息"
- Agent 在生成 SQL 时，能根据描述自动选择合适的表和字段
- 对于不同行业的数据库（零售、财务、医疗），描述能帮助 Agent 做出更准确的 SQL

---

## 7. 权限设计

| 功能 | admin | user |
|------|-------|------|
| 添加数据库 | ✅ | ❌ |
| 删除数据库 | ✅ | ❌ |
| 测试连接 | ✅ | ❌ |
| 导入 Schema | ✅ | ✅ (自己的数据库) |
| 生成描述 (Agent) | ✅ | ❌ |
| 编辑描述 | ✅ | ✅ (自己的数据库) |
| 使用数据库查询 | ✅ | ✅ (有权限的) |

> 通过现有的 `user_databases` 权限表控制用户对数据库的访问权限。

---

## 8. 实现顺序建议

| 阶段 | 任务 | 依赖 |
|------|------|------|
| **Phase 1** | SQLite 新增表 + Pydantic 模型 | 无 |
| **Phase 2** | 后端 Schema 导入 API + 持久化层 | Phase 1 |
| **Phase 3** | 后端 Schema Description Agent | Phase 1 |
| **Phase 4** | 前端 DatabaseManagerPage 页面 | Phase 2 |
| **Phase 5** | 前端 Schema 导入 + 描述编辑交互 | Phase 4 |
| **Phase 6** | Schema Prompt 改造使用动态描述 | Phase 3 |
| **Phase 7** | 测试 + 边界情况处理 | Phase 2-6 |

---

## 9. 技术要点

### 9.1 连通性测试

复用时已有的 `POST /api/database/test` 端点。测试成功后再允许添加数据库。

### 9.2 数据库类型扩展

当前 `DuckDBConnector` 是唯一实现的连接器。为了让 Schema 导入支持多种数据库类型，设计一个工厂函数：

```python
def create_connector(db_type: str, config: dict) -> DatabaseConnector:
    """根据数据库类型创建对应的连接器实例"""
    connectors = {
        "duckdb": DuckDBConnector,
        "postgres": PostgresConnector,  # 未来
        "mysql": MySQLConnector,        # 未来
    }
    cls = connectors.get(db_type)
    if not cls:
        raise ValueError(f"不支持的数据库类型: {db_type}")
    return cls(**config)
```

Schema 导入功能复用了 `DatabaseConnector.get_schema()` 接口，只要实现了该接口的数据库类型都能导入。

### 9.3 描述生成的健壮性

- LLM 可能返回不完整的 JSON，需要稳健的解析和重试逻辑
- 建议在 prompt 中使用 `response_format={"type": "json_object"}`（OpenAI 支持）
- 对非 OpenAI 的 LLM，增加 JSON 修复逻辑

### 9.4 大数据库的 Schema 导入

- 对于有上百张表的数据库，导入过程可能需要较长时间
- 建议使用异步任务 + 进度反馈（通过轮询或 SSE）
- 可考虑使用 `asyncio.gather` 并发读取表结构

---

## 10. 文件修改清单

### 后端新增文件

| 文件 | 说明 |
|------|------|
| `backend/app/persistence/schema.py` | Imported tables/columns 的持久化读写 |
| `backend/app/agent/describe_schema_agent.py` | Schema 描述生成 Agent |

### 后端修改文件

| 文件 | 变更 |
|------|------|
| `backend/app/persistence/__init__.py` | 新增 3 张表的 DDL |
| `backend/app/models/database.py` | 新增 Pydantic 模型 |
| `backend/app/routes/database.py` | 新增 4 个 API 端点 |
| `backend/app/db/schema.py` | 改造使用动态描述 |

### 前端新增文件

| 文件 | 说明 |
|------|------|
| `frontend/src/pages/DatabaseManagerPage.tsx` | 数据库管理页面 |
| `frontend/src/components/DbListPanel.tsx` | 左侧数据库列表面板 |
| `frontend/src/components/SchemaPanel.tsx` | Schema 展示 + 操作面板 |
| `frontend/src/components/DescriptionEditor.tsx` | 内联描述编辑组件 |
| `frontend/src/components/TableCard.tsx` | 单个表的卡片组件 |
| `frontend/src/components/ColumnRow.tsx` | 单列展示行组件 |
| `frontend/src/components/SchemaImportBar.tsx` | 导入 + 描述生成操作栏 |

### 前端修改文件

| 文件 | 变更 |
|------|------|
| `frontend/src/types/index.ts` | 新增类型定义 |
| `frontend/src/api/index.ts` | 新增 API 方法 |
| `frontend/src/components/Sidebar.tsx` | 增加"数据库管理"入口 |
| `frontend/src/App.tsx` | 注册新路由（条件渲染） |
