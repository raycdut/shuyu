# 前端架构重构方案

## P0（高优先级）

### 1. 引入路由系统

**方案**：使用 `react-router-dom` v7，建立 4 条主路由：

```
/                    → Chat 主页 (Sidebar + Chat + StatusBar)
/dashboard           → 数据看板
/admin               → 管理后台 (需 admin 角色)
/login               → 登录
/register            → 注册
```

**改动文件**：
- `main.tsx` → 包裹 `BrowserRouter`
- `App.tsx` → 移除状态驱动的页面切换，改为 `<Routes>` + `<Outlet>`
- 拆分为 `AppLayout.tsx`（头部 + 状态栏）+ `ChatPage.tsx`
- `AdminSettingsPage.tsx` → 通过 `useNavigate()` 返回
- 登录/注册页 → 跳转方式改为 `navigate('/')`

### 2. 看板数据持久化

**后端新增**：
```
GET    /api/dashboard/items     → 获取当前用户的看板条目
POST   /api/dashboard/items     → 添加看板条目
DELETE /api/dashboard/items/:id → 删除看板条目
```

**前端**：
- `store/index.ts` → 初始化时从后端加载 `dashboardItems`
- `api/index.ts` → 新增 `getDashboardItems()` / `addDashboardItem()` / `removeDashboardItem()`
- `MarkdownRenderer.tsx` 中的固定操作 → 调用 API + 更新 Store
- `Dashboard.tsx` → 加载后自动从后端同步

### 3. Zustand Store 拆分

从单体 Store 拆分为 3 个独立 Store：

| Store | 管理状态 |
|-------|---------|
| `useSessionStore` | sessions, activeSessionId, messages, isLoading |
| `useConfigStore` | llmConfig, safetyConfig, llmConnected |
| `useUIStore` | leftOpen, showDashboard, error, dashboardItems, mode |
| `useAuthStore` | user, token (保持不变) |

## P1（中优先级）

### 4. 拆分 AdminSettingsPage

将 847 行的单文件拆分为：

```
pages/admin/
├── tabs/
│   ├── LLMSettingsTab.tsx
│   ├── SafetySettingsTab.tsx
│   ├── UserManagementTab.tsx
│   └── ConfigLogTab.tsx
├── components/
│   ├── SettingSection.tsx
│   └── ToggleRow.tsx
└── AdminSettingsPage.tsx
```

### 5. 回调函数 + Props 优化

- 所有传递给 `React.memo` 组件的回调必须用 `useCallback`
- 所有对象/数组 props 必须用 `useMemo`
- 移除不必要的 props，改为在子组件内部直接 `useStore`

### 6. 消息 ID 生成改进

- 后端消息已有唯一 ID 时优先使用
- 无后端 ID 时使用 `role + content.slice(0,20) + timestamp`
- `nextMsgId()` 改为无副作用的纯函数

## P2（低优先级）

### 7. SSE 解析标准化

- 使用 `@microsoft/fetch-event-source` 替代手动 `fetch` + 逐行解析
- 自动处理重连、超时、多行事件

### 8. TanStack Query

- 替代 `useEffect` + `useCallback` 的数据加载模式
- 统一处理 loading/error/cache/refetch
