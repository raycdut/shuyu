# 变更记录 (Changes Log)

本文档记录了根据 `frontend-optimization-plan.md` 执行的前端优化变更。

## 2026-05-31 前端架构优化与功能扩展

### 1. 架构重构 (Phase 1)
- **引入 Zustand 状态管理**:
  - 创建了 `frontend/src/store/index.ts`，管理全局共享状态（会话、数据库、配置、UI 状态、看板）。
  - 移除了 `App.tsx` 中的冗余本地状态，通过 Store 进行统一管理。
- **业务逻辑解耦 (Custom Hooks)**:
  - 抽离 `useSessions`: 负责会话的 CRUD 逻辑。
  - 抽离 `useChatStream`: 负责复杂的 SSE 流解析和消息发送逻辑。
- **重构 App.tsx**: 将组件逻辑迁移至 Hook 和 Store，代码结构更清晰。

### 2. Markdown 渲染引擎升级 (Phase 2)
- **引入 react-markdown**: 替换了手写的正则解析。
- **支持 GFM 表格**: 配合 `remark-gfm` 插件，提供标准的表格支持。
- **代码高亮**: 集成 `react-syntax-highlighter` (Prism)，为 SQL 和代码块提供优质高亮。
- **封装 MarkdownRenderer**: 统一管理渲染逻辑，支持自定义组件。

### 3. 数据可视化集成 (Phase 3)
- **引入 Recharts**: 实现前端图表渲染。
- **智能图表识别**: 创建了 `ChartRenderer` 组件，根据数据特征（如日期、数值）自动选择折线图或柱状图。
- **图表/表格切换**: 在 `[Qn]` 标记旁增加了切换按钮，允许用户在表格和可视化图表间手动切换。
- **后端适配**: 修改了 `sql_tool.py`，使查询结果包含原始数据行，供前端图表使用。

### 4. 数据看板功能 (Phase 4)
- **固定到看板**: 在消息气泡中增加了“固定”按钮，支持将任意查询结果保存至看板。
- **看板展示**: 新增 `Dashboard` 组件，采用响应式网格布局展示已固定的图表和表格。
- **全局入口**: 在顶部工具栏增加了看板切换按钮。

### 5. 代码质量与规范
- **函数级注释**: 为所有主要函数和组件添加了详细的中文注释。
- **类型安全**: 更新了 `frontend/src/types/index.ts`，确保新功能的类型安全。

### 6. 后端 Bug 修复：图表数据丢失与 SSE 序列化

#### 6.1 修复 json.dumps 非 JSON 原生类型序列化崩溃 (🔴 致命)
- **问题**: DuckDB 查询结果中的 `datetime.date`、`datetime.datetime`、`decimal.Decimal` 类型无法被标准 `json.dumps` 序列化，导致 SSE 流在发送 `done` 事件时直接崩溃中断，前端收不到查询结果。
- **修复**: 在 `chat.py` 中新增 `_to_json_safe()` 递归转换函数和 `_make_event()` 封装方法，将所有非 JSON 原生类型自动转换为 ISO 字符串或浮点数。
- **范围**: 替换了 `chat_stream()` 中所有 `yield f"data: {json.dumps(...)}\n\n"` 调用为 `yield _make_event(...)`。

#### 6.2 修复 Session 不持久化 query_results (🟡 重要)
- **问题**: 深度分析完成后，`query_results` 存储在内存中，但刷新页面或切换会话后丢失。
- **修复**: 
  - `chat.py`: 在流式和非流式端点中，将 `query_results` 存入 `session.metadata["_query_results"]`。
  - `sessions.py`: 在 `get_session_messages` 中，从 session metadata 中读取 `_query_results` 并附加到最后一个 assistant 消息返回。

#### 6.3 修复前端并发进度更新覆盖最终结果
- **问题**: SSE 流关闭前的延迟事件（如 `thinking`/`step`）可能因 `updateProgress` 误更新将最终消息重新标记为进度状态。
- **修复**: `useChatStream.ts` 中 `updateProgress` 增加 `m.isProgress` 守卫检查，只更新仍处于进度状态的消息。

#### 6.4 修复 SSE 流跨 chunk 边界导致 done 事件丢失
- **问题**: 原 SSE 解析器按 `\n` 分割数据行，每条 `data:` 行独立解析。当 `done` 事件的 JSON 体较大时（如包含大量 `query_results`），可能被 HTTP chunked 传输截断，跨多个 `reader.read()` 调用分片到达。被截断的半截 JSON 无法解析，事件被静默丢弃，导致进度条卡死、最终结果不显示。
- **修复**:
  - 改用 `\n\n`（SSE 事件终止符）作为解析粒度，确保只在收到完整事件后才做 JSON 解析。
  - 引入 `partialDataLine` 累积缓冲，跨 chunk 积累 `data:` 后的 JSON 片段，直到可完整解析。
  - 抽离 `handleEvent()` 函数，消除剩余 buffer 处理中的空处理分支，确保流结束时缓冲区中的 `done` 事件也能正确渲染。

#### 6.5 修复 LLM 报告生成返回空内容导致结果不显示
- **问题**: LLM 在报告生成或审核补充阶段可能返回空内容（`content: ''`），导致 `done` 事件的 `content` 为空，前端只显示"分析完成。"而看不到实际分析内容。
- **修复**:
  - `_phase_report`: 增加空内容兜底，从对话历史中提取最后几条消息作为降级报告。
  - `_phase_report_reflect`: 记录补充前的报告内容，当 LLM 重新生成返回空时保留上一版有效报告。
  - 增加最终兜底检查：如果整个审核循环结束后报告仍为空，回退到原始报告或对话摘要。
  - 前端 `useChatStream.ts`: 移除加载指示器在质量模式下的冗余显示（由进度面板替代）。
