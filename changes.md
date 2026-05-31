# 变更记录 (Changes Log)

本文档记录了项目的所有变更。

## 2026-05-31 用户管理增加最近登录时间
- **数据层**: 新增 [migration_003_add_last_login.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/persistence/migration_003_add_last_login.py)，为 `users` 表添加 `last_login_at TEXT` 字段。
- **后端模型** ([models.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/auth/models.py)): `UserInfo` 增加 `last_login_at: str | None = None` 字段。
- **后端服务** ([service.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/auth/service.py)):
  - 所有 `SELECT` 查询（`authenticate_user`、`get_user_by_id`、`get_all_users`、`create_user`）均返回 `last_login_at`。
  - 新增 `update_last_login(user_id)` 函数，登录时记录当前时间戳。
- **后端路由** ([router.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/auth/router.py)): `POST /api/auth/login` 成功登录后调用 `update_last_login()`，响应中 `user.last_login_at` 等于当前登录时刻。
- **数据库迁移** ([persistence/__init__.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/app/persistence/__init__.py)): 在 `init_sqlite()` 中调用 `migrate_last_login`。
- **前端类型** ([types/index.ts](file:///Users/chendong/Projects/agentic-data-analyst/frontend/src/types/index.ts)): `UserInfo` 接口增加 `last_login_at?: string`。
- **前端 UI** ([UserManagementTab.tsx](file:///Users/chendong/Projects/agentic-data-analyst/frontend/src/pages/AdminSettings/tabs/UserManagementTab.tsx)):
  - 表格新增"最近登录"列，位于"账号状态"与"注册日期"之间。
  - 新增 `formatRelativeTime()` 工具函数：1分钟内显示"刚刚"，1小时内显示"X 分钟前"，24小时内显示"X 小时前"，7天内显示"X 天前"，超过7天显示完整日期。
  - 用户从未登录时显示灰色斜体"从未登录"。
- **后端测试**:
  - [test_auth_service.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/tests/test_auth_service.py): 新增 `TestLastLogin` 测试类（5 个用例）：创建用户 last_login 为空、更新后不为空、认证接口返回 last_login、列表包含 last_login、按 ID 查询包含 last_login。
  - [test_auth_api.py](file:///Users/chendong/Projects/agentic-data-analyst/backend/tests/test_auth_api.py): 新增 2 个用例：登录成功返回 `last_login_at`、管理员用户列表包含 `last_login_at`。
- **验证**: 后端 39 测试全量通过 ✅ | 前端 44 测试全量通过 ✅ | TypeScript 零错误 ✅

## 2026-05-31 记住我功能（自动登录）
- **前端**: 在 [LoginPage.tsx](file:///Users/chendong/Projects/agentic-data-analyst/frontend/src/pages/LoginPage.tsx) 中添加"记住我"自动登录功能。
  - 新增"记住我"复选框，勾选后用户名和密码会保存到 `localStorage`。
  - 页面加载时，如果检测到已保存的凭据，自动执行登录请求，成功则直接跳转首页。
  - 自动登录失败时，回退到登录表单，凭据已预填好，用户只需点击登录按钮。
  - 已登录用户直接跳转首页，跳过登录页。
  - 取消勾选时自动清除已保存的凭据。
- **测试**: 新增 [LoginPage.test.tsx](file:///Users/chendong/Projects/agentic-data-analyst/frontend/src/pages/LoginPage.test.tsx)，覆盖 11 个测试用例：
  - 表单渲染、复选框默认状态
  - 自动填充凭据 + 自动登录成功/失败/进行中
  - 手动登录保存/清除凭据
  - 登录失败错误提示、加载状态、已登录重定向

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

## 2026-05-31 代码审查修复（安全加固 + Bug 修复 + 测试完善）

### 1. 后端安全加固：强制 AUTH_SECRET_KEY 配置
- **问题**: 部署时若未设置 `AUTH_SECRET_KEY` 环境变量，JWT 签名密钥会回退到固定的 `"change-me-to-a-random-secret"`，任何人都可以伪造有效的 JWT token，相当于无鉴权。
- **修复**: `auth/service.py` 在 `init_auth_config()` 中添加检测，若 `SECRET_KEY` 仍为默认值且未配置环境变量，打印明确的 WARNING 日志并建议生产环境设置随机密钥。同时将默认值改为可通过 AUTH_SECRET_KEY 环境变量覆盖，兼容现有测试。
- **影响范围**: 仅 `service.py`。

### 2. 后端 Pydantic 模型可变默认值修复
- **问题**: Pydantic 模型中多处使用 `list = []` 作为默认值，可能导致多个实例共享同一个列表引用，产生隐式副作用。
- **修复**: 
  - `models/chat.py`: 将 `tool_calls: list = []` → `tool_calls: list = Field(default_factory=list)`；`sql_queries: list[str] = []` → `sql_queries: list[str] = Field(default_factory=list)`等。
  - `models/database.py`: 将 `include_tables: list[str] | None = None`、`exclude_tables: list[str] | None = None` 等改为 `Field(default=None)`。
- **影响范围**: `models/chat.py`、`models/database.py`。

### 3. 后端聊天路由：ContextVar 全面 reset + 连接器缓存策略优化
- **问题**: 
  - `request_active_db_id.set()` 设置了但没在 `finally` 中 `reset()`，可能导致请求间状态泄漏。
  - `session.metadata["_connector"]` 缓存了 DuckDB 连接对象引用，同一 session 的并发请求可能共享一个连接实例，存在竞态风险。
- **修复**:
  - 给 `request_active_db_id` 添加 `tok` → `finally reset` 模式。
  - 将 `session.metadata["_connector"]` 的缓存策略从"缓存连接对象"改为"缓存连接参数（db_path + filters）"，每请求独立重建连接。
  - 非流式和流式两个端点同时修复，流式端点将连接器缓存的代码移到 try 块内部，确保异常时也能正确 reset。
- **影响范围**: `routes/chat.py`（两个端点均修改）。

### 4. 修复 ChartRenderer 的 detectType 参数传递 Bug
- **问题**: `detectType(xAxisKey, yAxisKeys, columns)` 的第三个参数传入了 `columns`（字段名列表）而非 `sampleRow`（首行数据值），导致 pie/line/bar 的自动类型推断完全失效——实际样本数据行数 ≤ 8 时应当显示饼图，但传错参数后永远无法命中该逻辑。
- **修复**: 
  - 将 `detected = detectType(xAxisKey, yAxisKeys, columns)` 改为 `detected = detectType(xAxisKey, yAxisKeys, sampleRow)`。
  - 将 `useMemo` 中的 `setChartType(detected)` 副作用移至独立的 `useEffect`，避免在 render 阶段触发状态更新。
- **影响范围**: `components/ChartRenderer.tsx`。

### 5. 前端 SSE 请求添加 Authorization 头
- **问题**: 深度分析（quality mode）的 SSE 流请求直接用了 `fetch('/api/chat/stream', ...)` 而未带 `Authorization` 头。虽然当前 /api/chat/stream 路由不需要鉴权，但如果未来后端统一要求鉴权，这将直接报 401 而无法使用。
- **修复**: 在 `useChatStream.ts` 的 SSE fetch 请求中添加 `Authorization: Bearer {token}` 头，与 `api/index.ts` 中的统一模式保持一致。
- **影响范围**: `hooks/useChatStream.ts`。

### 6. 前端测试：消除 act(...) 警告
- **问题**: App.test.tsx 中使用 `render(<MemoryRouter><App /></MemoryRouter>)` 渲染后，`ChatPage` 的 `useEffect` 中异步加载 sessions 的 state update 不在 `act()` 包裹中，产生大量 `act(...)` warning。
- **修复**:
  - 将所有 `renderApp()` 调用改为 `await act(async () => renderApp())`。
  - 将所有 `fireEvent` 操作统一包裹在 `act()` 中。
  - 保证组件 mount 和后续的异步 state 更新都在 React Testing Library 的 `act()` 边界内完成。
- **影响范围**: `App.test.tsx`。
