# 前端架构优化与功能扩展计划

本文档旨在梳理当前前端架构的瓶颈，并制定后续功能扩展（如可视化、看板、多 Agent 交互）的优化路径。

---

## 1. 架构层面优化 (Architecture)

### 1.1 引入专门的状态管理 (Zustand)
**状态**: 
- ✅ 核心 Store 拆分（Session, Config, UI, Auth）— 已完成
- ✅ **Selector 订阅**: 全量推行 selector-based 订阅模式已完成，项目中零解构订阅残留
- ⏳ **Action 封装**: 将复杂的业务逻辑（如多状态同步更新）封装在 Store 的 Action 中

### 1.2 业务逻辑解耦 (Custom Hooks)
**状态**: 
- ✅ 已抽离 `useChatStream` 和 `useSessions`
- ✅ **SSE 稳定性评估**: 当前 SSE 为单请求-流响应模式，`@microsoft/fetch-event-source` 自动重连不适用，现有实现已通过 35 项测试
- ⏳ **API 层抽象**: 考虑引入 React Query (TanStack Query) 管理静态数据缓存

### 1.3 组件架构优化 (Memoization)
**状态**:
- ✅ **原子化拆分**: SessionItem, DbTableNode 已拆分为独立文件；MessageBubble 已有独立文件且含 React.memo
- ✅ **全量 Memo**: 所有叶子组件已包含 React.memo；Sidebar 回调已改用 useCallback 稳定引用；Hooks 层 useCallback 审计通过

---

## 2. 功能扩展规划 (New Features)

### 2.1 增强数据分析体验
- **消息 ID 优化**: 采用自增计数器或 UUID 替代 `Date.now()`，避免快速发送消息时的 ID 冲突。
- **进度可视化**: 在深度分析模式下，提供更丰富的中间步骤展示（如展示正在生成的 SQL 预览）。

### 2.2 数据可视化 (Data Visualization)
**目标**: 让 Agent 返回的数据不只是表格，还能自动生成图表。
**路径**:
- 引入 **Recharts**。
- **智能识别**: 当查询结果包含“时间+数值”或“分类+数值”时，自动渲染折线图或柱状图。
- **交互增强**: 支持点击图表元素进行下钻分析（Drill-down）。

### 2.3 数据看板 (Dashboard Mode)
**目标**: 允许用户将重要的查询结果固定到看板，实现持久化监控。
**路径**:
- 在 `MessageBubble` 中增加“固定到看板”按钮。
- 新增 `Dashboard` 页面，支持拖拽布局（React Grid Layout）。

---

## 3. 工程化与测试 (Engineering)

### 3.1 测试稳定性优化
- **Mock 策略**: 针对拆分后的 Store 建立统一的 Mock 配置文件。
- **异步处理**: 规范化测试中的 `act` 和 `waitFor` 使用，避免超时和不稳定的测试结果。

### 3.2 性能监控
- 引入简单的性能埋点，记录 SSE 首包延迟、大表渲染时间等关键指标。

---

## 4. 实施路线图 (Updated)

1. **Phase 1 (架构重构 - ✅ 已完成)**: Store 拆分、AdminSettings 拆分、核心页面适配。
2. **Phase 2 (性能与稳定性 - ✅ 已完成)**: Selector 订阅优化、组件原子化拆分、测试稳定性加固、useCallback 全量审计。
3. **Phase 3 (能力增强 - ✅ 已完成)**: Recharts 集成、智能图表类型检测（折线/柱状/饼图自动切换）、多 Y 轴支持、消息气泡内联图表展示。
4. **Phase 4 (看板与持久化 - 进行中)**: Dashboard 功能实现，支持跨会话的数据聚合。
