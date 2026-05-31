# Store 拆分变更记录

## 变更说明

将单体的 `store/index.ts` Zustand Store 拆分为 3 个独立 store 文件，以减少不必要的组件重渲染。

## 变更内容

### 新增文件

1. **`store/sessionStore.ts`** — 会话管理 Store
   - `sessions` / `activeSessionId` / `messages` / `isLoading`
   - Actions: `setSessions` / `setActiveSessionId` / `setMessages` / `setIsLoading`

2. **`store/configStore.ts`** — 配置管理 Store
   - 数据库状态: `databases` / `activeDbId` / `mode` / `schema`
   - LLM 配置: `llmConnected` / `llmConfig`
   - 安全配置: `safetyConfig`
   - Actions: `setDatabases` / `setActiveDbId` / `setMode` / `setSchema` / `setLlmConnected` / `setLLMConfig` / `setSafetyConfig`

3. **`store/uiStore.ts`** — UI 状态 Store
   - 面板状态: `leftOpen` / `rightOpen` / `showDashboard` / `error`
   - 看板条目: `dashboardItems`
   - Actions: `setLeftOpen` / `setRightOpen` / `setShowDashboard` / `setError` / `addDashboardItem` / `removeDashboardItem` / `setDashboardItems`
   - 导出 `DashboardItem` 类型

### 修改文件

- **`store/index.ts`**
  - 移除内联 `DashboardItem` 接口定义，改为从 `./uiStore` 导入并重新导出
  - 末尾添加 3 个独立 Store 的重新导出（`useSessionStore` / `useConfigStore` / `useUIStore`）
  - 原 `useStore` 单体 Store 保持不变

## 向后兼容性

- ✅ `import { useStore } from '../store'` — 仍然可用
- ✅ `import { DashboardItem } from '../store'` — 仍然可用（通过重新导出）
- ✅ 新代码可按需选择性导入: `import { useSessionStore } from '../store'`
