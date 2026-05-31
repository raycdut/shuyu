# Phase 2 优化任务 — Frontend Refactor Prompt

## 项目背景
Agentic Data Analyst 前端架构正在从单体状态管理迁移到模块化 Store (Zustand)，并进行组件解耦以提升性能和可维护性。

## 当前进度
- [x] 核心 Store 拆分 (Session, Config, UI, Auth)
- [x] AdminSettingsPage 巨无霸组件拆分
- [x] 核心页面 (AppLayout, ChatPage) 的 Store 订阅优化
- [x] 解决 Vitest 测试超时和稳定性问题

## 需要你执行的任务

### 1. 组件库优化与性能审计 (Performance & Component Audit)
目标：减少不必要的重渲染，提高组件响应速度。

- **1.1 剩余页面的 Store 订阅优化**
  - 修改 `DatabaseManagerPage.tsx`, `LoginPage.tsx`, `RegisterPage.tsx`, `Dashboard.tsx`。
  - 将 `const { x, y } = useStore()` 模式改为 `const x = useStore(s => s.x)` 模式，确保组件只在依赖的特定状态变化时重渲染。

- **1.2 核心组件拆分与 Memoization**
  - **Sidebar.tsx**: 
    - 将 `SessionItem` 和 `DbTableNode` 提取到独立文件 `src/components/Sidebar/` 目录下。
    - 为这些子组件添加 `React.memo`。
    - 确保父组件传递的 props (如 `onSelectSession`) 都经过 `useCallback` 处理。
  - **Chat.tsx**:
    - 确保 `MessageBubble` 的渲染性能。
    - 提取复杂的渲染逻辑（如代码块、表格、进度面板）为独立子组件并应用 `React.memo`。

- **1.3 useCallback 全量审计**
  - 遍历所有使用 `useConfigStore`, `useSessionStore` 的自定义 Hook 和页面组件。
  - 确保所有传递给子组件的事件处理函数 (Handlers) 都被 `useCallback` 包裹。

### 2. SSE 增强与稳定性 (Robust SSE Handling)
目标：提升深度分析模式下数据流的鲁棒性。

- **2.1 引入 @microsoft/fetch-event-source**
  - 安装并替换 `useChatStream.ts` 中手写的 `fetch` + `ReadableStream` 解析逻辑。
  - 利用该库提供的自动重连机制，处理不稳定的网络环境。
  - 完善错误处理逻辑，当 SSE 连接断开或返回错误事件时，在 UI 上提供清晰的重试或报错信息。

### 3. 基础能力提升 (Foundation Improvements)
- **3.1 消息 ID 生成策略**
  - 修改 `src/types/index.ts` 中的 `nextMsgId` 函数。
  - 停止使用 `Date.now()` 这种可能在极短时间内产生冲突的方式。
  - 改用更稳健的策略（如简单的自增计数器结合 UUID 或前缀）。

- **3.2 Admin Settings 细节完善**
  - 检查 `src/pages/AdminSettings/tabs/` 下的各个组件。
  - 确保配置保存操作 (onSave) 的原子性，避免中间状态导致 UI 闪烁。
  - 统一配置项的校验逻辑。

## 执行约束
1. **不破坏现有功能**：每次重构后需运行 `npm test` 确保测试全部通过。
2. **代码风格一致性**：遵循现有的 Tailwind CSS 命名规范和 TypeScript 类型定义。
3. **注释规范**：为新拆分的组件和关键 Hook 函数添加详细的 JSDoc 注释。
4. **Markdown 记录**：在 `docs/changes-2026-05-31.md` 中记录每一项重大变更。
