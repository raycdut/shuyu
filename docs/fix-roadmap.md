# Shuyu 修复 Roadmap

按优先级从高到低，每项含影响评估和改进方案。

---

### 2026-05-31: 强制 DeepSeek 输出 JSON 格式 + 修复 `sql` 参数兼容
- **强制 JSON**：Plan/PlanReflect 阶段改用 `response_format={"type": "json_object"}` 让 DeepSeek 输出严格 JSON，消除 `xml`/`<｜｜DSML｜｜tool_calls>` 格式泄漏到正文的问题
  - PLAN_PROMPT、PLAN_REFLECT_PROMPT 改为 JSON Schema 格式
  - `_parse_plan_steps` 改为直接从 JSON 解析 steps/sql
  - 前端计划展示也调整为 JSON 解析渲染
  - 测试 mock 同步更新为 JSON 格式响应
- **sql 参数兼容**：`handle_query_database` 新增可选 `sql` 参数，收到原始 SQL 时跳过 LLM 生成步骤直接执行，解决 `_execute_step` 传 raw SQL 给模型、模型用错参数名的问题
  - 新增 `_execute_sql()` 独立函数
  - 工具注册将 `sql` 设为可选参数（`required=[]`）
  - 更新 `_execute_step` 的 prompt 显式告知模型使用 `sql=...`

## 🔴 P0 — 必须尽快修

### 1. LLM 调用 timeout

**当前**: `call_llm()` 无 timeout，API 卡住时前端无限等待

**方案**: 
```python
client.chat.completions.create(..., timeout=30)
```
SQL Tool 内的 LLM 调用也加 timeout。Agent loop 本身已经有 10 轮上限。

**文件**: `app/llm.py`, `app/agent/tools/sql_tool.py`
**影响**: 用户不再遇到无限转圈

---

### 2. SQL 执行安全

**当前**: LLM 生成的 SQL 直接执行，只靠 system prompt 约束

**方案**: 
- 执行前检查：必须是 SELECT，不能含 DROP/ALTER/DELETE/INSERT
- 用 `sqlparse` 库解析 SQL 做静态校验

**文件**: `app/agent/tools/sql_tool.py`
**影响**: 防止 prompt injection 导致数据破坏

---

### 3. LLM 调用错误重试

**当前**: 429/502 直接抛异常

**方案**: 自动重试 3 次，退避等待
```python
for attempt in range(3):
    try:
        return await client.chat.completions.create(...)
    except (RateLimitError, APIError) as e:
        if attempt == 2: raise
        await asyncio.sleep(2 ** attempt)
```

**文件**: `app/llm.py`
**影响**: 临时故障不再弹错误

---

## 🟡 P1 — 重要

### 4. Token 计数 + 成本追踪

**当前**: 日志不记 token

**方案**: 从 API 响应中读 `usage` 字段，记到日志和 `_config_db`

**文件**: `app/llm.py`
**影响**: 可追踪每次查询成本

---

### 5. Schema 按需注入

**当前**: 210 张表全量注入 prompt

**方案**: 
1. 先调用 LLM 判断问题涉及哪些表
2. 只注入相关表的 schema
3. 或者按 schema 分类（dim/fct/stg）选择性注入

**文件**: `app/routes/chat.py`
**影响**: 减少 50-80% schema token，提升准确率

---

### 6. Prompt 结构化

**当前**: 纯文本拼接 system prompt

**方案**: 改用 XML 模板，对推理模型更友好

**文件**: `app/agent/loop.py` (system_prompt)
**影响**: 模型响应一致性提高

---

## 🟢 P2 — 优化

### 7. 会话内复用 DuckDB 连接

**当前**: 每次聊天都新建连接

**方案**: 在 session 生命周期内缓存 connector，用完后 close

**文件**: `app/routes/chat.py`
**影响**: 同一会话连续问题省掉重复的 schema 查询

---

### 8. Agent 中间状态流式输出

**当前**: 前端只显示"正在分析…"

**方案**: 
- 后端用 Server-Sent Events (SSE) 替代 POST
- 每步推送给前端：思考中 → 查询中 → 返回结果
- 前端逐步展示

**文件**: 新 route + 前端 Chat 组件改造
**影响**: 用户体验大幅提升，类似 ChatGPT 的思考过程展示

---

## 变更记录

### 2026-05-31

- 后端引入 request-local 上下文（ContextVar），替代全局的 per-request 状态，避免并发串扰
- SQL 查询收集改为请求级收集器，fast/quality 模式统一从收集器返回 `sql_queries`
- SQL 工具增加结构化查询结果收集 `query_results`（兼容旧的文本 tool 输出），API 与 SSE done 事件返回该字段
- quality 模式 SSE 的 done 事件补充 `sql_queries` 字段，前端可稳定展示本次查询列表
- AdvancedAgent 的步骤成功判定改为基于 SQL 工具成功标记，减少小结果误判与无效重试
- SSE quality 模式在完成后不再强制 cancel agent_task，确保收尾与会话写入更稳定
- stream 路由复用 session 内 schema/full_schema 缓存，减少重复 get_schema/build_schema_prompt
- SimpleAgent 升级：摘要式压缩历史 + 基于参数签名的循环检测，减少发散与重复查询
- 前端消息气泡在报告末尾增加“查询语句”图标，鼠标悬停可查看本次用到的 SQL 列表
- 未选择数据库时，后端 chat/stream 直接返回提示（不再进入 quality 计划/执行流程），前端深度模式也会先行拦截

---
