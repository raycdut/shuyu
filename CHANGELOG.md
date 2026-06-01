# Changelog

## 2026-06-01 — 前端组件复用重构

### 新增通用组件
- `PageHeader` — 统一页面标题区（title + subtitle + actions）
- `LoadingState` — 统一加载状态
- `EmptyState` — 统一空状态（图标 + 提示 + 操作按钮）
- `Modal` — 通用模态框（title/subtitle/footer/size/backdropBlur）
- `DataTable<T>` — 泛型表格组件（columns/data/render/emptyMessage）
- `AuthLayout` — 登录/注册页面布局

### 重构文件（15 个文件，+522 -605 行）

| 文件 | 变更 |
|------|------|
| `Common.tsx` | 新增 PageHeader/LoadingState/EmptyState；SettingSection 增加 compact prop |
| `ConfigPanel.tsx` | 内联 Section → SettingSection(compact)；内联 ToggleRow → CheckRow |
| `DBConnectModal.tsx` | 改用 Modal 组件 |
| `LLMSettingsTab.tsx` | ModelDialog 改用 Modal + PageHeader |
| `PromptManagementTab.tsx` | 编辑器改用 Modal |
| `UserManagementTab.tsx` | 改用 PageHeader + DataTable + LoadingState |
| `ConfigLogTab.tsx` | 改用 PageHeader + DataTable + LoadingState |
| `DashboardTab.tsx` | 改用 PageHeader + LoadingState |
| `SafetySettingsTab.tsx` | 改用 PageHeader |
| `AdvancedSettingsTab.tsx` | 改用 PageHeader |
| `StorageSettingsTab.tsx` | 改用 PageHeader |
| `DatabaseManagementTab.tsx` | 样式统一(ink/tea/celadon 色系)；改用 PageHeader/EmptyState/LoadingState |
| `LoginPage.tsx` | 改用 AuthLayout |
| `RegisterPage.tsx` | 改用 AuthLayout |

### 测试
- 126 项前端测试全部通过
- TypeScript 类型检查通过
