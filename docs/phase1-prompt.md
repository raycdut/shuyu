# Phase 1 开发任务 — Reasonix prompt

## 项目

Agentic Data Analyst — 开源的对话式数据分析 Agent，类似 Databricks Genie。用户用自然语言查数据库，不需要写 SQL。

```
仓库: ~/projects/agentic-data-analyst/
技术栈: Python 3.11, FastAPI, DuckDB, ChromaDB, OpenAI SDK
前端: HTML/CSS/JS 或 React
目标用户: 小公司老板、非技术人员
```

## 当前状态

项目 scaffold 已完成：
- `config.example.yaml` — 配置模板
- `Dockerfile` + `docker-compose.yml` — 部署
- `requirements.txt` — 依赖
- `docs/ui-spec.md` — 前端设计规格（三栏布局）

## 需要你开发的模块

### Phase 1.1 — 后端核心（优先）

按以下顺序实现：

**1. `app/config.py` — 配置加载**
- 读取 config.yaml
- 支持环境变量覆盖（LLM_API_KEY, DB_PATH 等）
- 返回 Config dataclass/Pydantic model

**2. `app/db/base.py` — 数据库连接器抽象**
- `DatabaseConnector` 抽象类
- 方法: connect(), disconnect(), get_schema(), execute(sql), test_connection()
- `TableInfo` / `ColumnInfo` / `QueryResult` 数据结构

**3. `app/db/duckdb.py` — DuckDB 连接器实现**
- 继承 DatabaseConnector
- get_schema() 从 information_schema 自动发现表结构
- 支持 include_tables / exclude_tables 过滤

**4. `app/agent/tools/registry.py` — 工具注册中心**
- `Tool` class: name, description, parameters, handler
- `ToolRegistry`: register, get, list, call_tool

**5. `app/agent/loop.py` — ReAct Agent Loop（自建，不用 LangChain）**
- AgentLoop class
- run(messages) → 迭代：LLM 调用 → 工具执行 → 观察结果
- 支持 OpenAI-compatible tool calling
- 最多 10 次迭代上限

**6. `app/session/manager.py` — 会话管理**
- Session: 消息列表 + sliding window 压缩
- SessionManager: 创建/获取会话，定时清理过期会话
- 超过 20 条消息自动压缩旧消息为摘要

**7. `app/main.py` — FastAPI 入口**
- POST /api/chat — 接收 {message, session_id}，返回 {reply, session_id}
- GET /api/schema — 返回数据库结构（调试用）
- GET / — 返回聊天界面 HTML
- 启动时自动加载 config、连接数据库、注册工具

### Phase 1.2 — 配置存储设计

所有配置存在 DuckDB `analytics.db` 的不同表里（不用 YAML/JSON）：

| 表名 | 用途 | 字段 |
|------|------|------|
| `_config_llm` | LLM 提供商配置 | id, name, provider_type, api_key, api_base, model, is_active |
| `_config_databases` | 数据库连接信息 | id, name, db_type, connection_string, auth_json, include_tables, exclude_tables |
| `_config_settings` | 全局设置（键值对） | key, value (JSON) — 如当前活跃DB、安全选项 |
| `_sessions` | 会话列表 | id, title, db_id, created_at, updated_at |
| `_messages` | 聊天消息 | id, session_id, role, content, tool_calls_json, created_at |

配置表用 `_` 前缀区分与用户业务表。

### Phase 1.2 — API 扩展

- POST /api/database/connect — 添加并连接新的数据库
- POST /api/config — 更新运行时配置（LLM 提供商等）
- GET /api/config — 读取当前配置
- GET /api/sessions — 查看活跃会话

### Phase 1.3 — 前端（按 ui-spec.md）

三栏布局：
- 左栏：数据库列表 + 添加按钮
- 中栏：聊天窗口（消息气泡 + 表格渲染）
- 右栏：配置面板（LLM + 安全 + 高级设置）

## 约束

1. **不引入 LangChain / LangGraph / LlamaIndex** — Agent loop 自己写
2. OpenAI SDK 版本 >= 1.0（新客户端 API）
3. 所有 LLM 调用通过一个统一函数，方便审计
4. 隐私优先：默认不把查询结果发给 LLM
5. 全中文界面
