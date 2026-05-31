# 变更日志 — 用户认证与配置管理系统

## 2025-05-31

### Phase 1: 后端 Auth 基础设施 ✅

#### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/app/auth/__init__.py` | Auth 模块入口 |
| `backend/app/auth/models.py` | Pydantic 模型 |
| `backend/app/auth/service.py` | 核心业务逻辑 |
| `backend/app/auth/middleware.py` | FastAPI 依赖注入 |
| `backend/app/auth/router.py` | 认证路由 |
| `backend/tests/conftest.py` | 测试配置 |
| `backend/tests/test_auth_service.py` | 18 个单元测试 |
| `backend/tests/test_auth_api.py` | 14 个集成测试 |

#### 修改文件

| 文件 | 变更 |
|------|------|
| `backend/requirements.txt` | 新增 bcrypt, pyjwt |
| `backend/app/persistence/__init__.py` | 新增 users 表、user_databases 表、sessions.user_id |
| `backend/app/main.py` | 注册 auth_router |

---

### Phase 2: 前端 Auth ✅

#### 新增文件

| 文件 | 说明 |
|------|------|
| `frontend/src/store/authStore.ts` | Zustand auth store |
| `frontend/src/pages/LoginPage.tsx` | 登录页面 |
| `frontend/src/pages/RegisterPage.tsx` | 注册页面 |

#### 修改文件

| 文件 | 变更 |
|------|------|
| `frontend/src/types/index.ts` | 新增 auth 相关类型 |
| `frontend/src/api/index.ts` | 新增 auth + admin API 方法，JWT 自动附加 |
| `frontend/src/App.tsx` | 集成 auth 流程 |
| `frontend/src/App.test.tsx` | 适配 auth mock |

---

### Phase 3: 后端配置管理 API ✅

#### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/app/admin_config/__init__.py` | 配置管理模块入口 |
| `backend/app/admin_config/service.py` | 配置服务：读写/合并/日志 |
| `backend/app/admin_config/router.py` | 配置路由 |
| `backend/tests/test_admin_config_service.py` | 15 个单元测试 |

#### 修改文件

| 文件 | 变更 |
|------|------|
| `backend/app/persistence/__init__.py` | 新增 system_config / user_configs / config_changelog 表 |
| `backend/app/main.py` | 注册 admin_config_router |
| `backend/app/routes/config.py` | GET /api/config 改为可选 auth + 合并逻辑 |

#### 新增 API 端点

| 方法 | 路径 | 权限 |
|------|------|------|
| GET | `/api/admin/config` | admin |
| PUT | `/api/admin/config` | admin |
| PATCH | `/api/admin/config` | admin |
| GET | `/api/admin/config/changelog` | admin |
| GET | `/api/user/config` | 登录 |
| PUT | `/api/user/config` | 登录 |
| GET | `/api/user/config/available` | 登录 |
| GET | `/api/user/config/history` | 登录 |

---

### Phase 4: 前端配置页面 ✅

#### 新增文件

| 文件 | 说明 |
|------|------|
| `frontend/src/pages/AdminSettingsPage.tsx` | 管理员配置页面（7 个 Tab） |

#### 修改文件

| 文件 | 变更 |
|------|------|
| `frontend/src/types/index.ts` | 新增 SystemConfig / UserConfig / UserAvailableOptions 类型 |
| `frontend/src/api/index.ts` | 新增 admin/user config API 方法 |
| `frontend/src/App.tsx` | 顶部栏添加系统设置入口（仅 admin 可见），渲染 AdminSettingsPage |

---

### Phase 5: UI 布局优化与美化 ✅

#### 修改文件

| 文件 | 变更 |
|------|------|
| `frontend/src/pages/AdminSettingsPage.tsx` | 重构布局：左侧导航栏加宽并添加阴影，右侧工作区采用 `flex-1` 撑满并优化内边距。 |
| `frontend/src/pages/AdminSettingsPage.tsx` | 子组件美化：LLM 提供商列表采用卡片布局，开关项改为 Switch 风格，添加渐入动画。 |
| `frontend/src/pages/AdminSettingsPage.tsx` | 代码规范：为所有函数添加了详细的 JSDoc 注释。 |

#### 关键改进
- **宽度自适应**: 移除了导致布局过窄的 `max-w-3xl` 限制，确保在大屏幕下也能充分利用空间，同时通过 `max-w-6xl mx-auto` 保持了良好的可读性。
- **视觉层级**: 重新设计了侧边栏与内容区的对比度，增加了分隔线与悬停效果，提升了专业感。
- **交互体验**: 统一了输入框、下拉框与按钮的宽度，增加了操作反馈（如保存中状态、hover 效果）。

---

### 测试结果

| 层 | 结果 |
|----|------|
| 后端 pytest | **47/47 passed** |
| 前端 TypeScript | **0 errors** |
| 测试覆盖 | auth service 单元测试 + auth API 集成测试 + config service 单元测试 |
