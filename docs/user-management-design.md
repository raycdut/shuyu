# 用户管理系统设计文档

## 1. 概述

当前系统为单用户架构，无认证机制。本文档设计一套完整的用户管理系统，支持多用户注册登录、会话隔离、以及管理员对数据库访问权限的控制。

### 核心需求

1. 默认第一个注册用户为管理员
2. 其他用户可创建账号登录
3. 每个用户拥有独立的会话（Session）
4. 管理员可为用户分配可访问的数据库

---

## 2. 数据模型

### 2.1 新增表

#### users（用户表）

```sql
CREATE TABLE users (
    id          TEXT PRIMARY KEY,                -- UUID
    username    TEXT UNIQUE NOT NULL,            -- 用户名（登录用）
    password_hash TEXT NOT NULL,                 -- bcrypt 哈希密码
    role        TEXT NOT NULL DEFAULT 'user'     -- 'admin' | 'user'
                         CHECK(role IN ('admin', 'user')),
    is_active   INTEGER NOT NULL DEFAULT 1,      -- 软删除/禁用
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

#### user_databases（用户-数据库权限关联表）

```sql
CREATE TABLE user_databases (
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    database_id TEXT NOT NULL REFERENCES databases(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, database_id)
);
```

### 2.2 现有表修改

#### sessions 表 — 新增 user_id 字段

```sql
ALTER TABLE sessions ADD COLUMN user_id TEXT REFERENCES users(id);
```

说明：
- `user_id` 为 `NULL` 表示旧数据（兼容迁移），新会话必须关联用户
- 查询会话时按 `user_id` 过滤，实现用户隔离
- `DELETE CASCADE` 确保用户删除时其会话一并清理

---

## 3. 后端设计

### 3.1 技术选型

| 模块 | 技术 |
|------|------|
| 密码哈希 | `bcrypt`（`pip install bcrypt`） |
| 认证方式 | JWT（`pip install pyjwt`） |
| Token 存储 | 无状态，JWT 本身包含用户信息 |
| 中间件 | FastAPI `Depends()` 依赖注入 |

### 3.2 新增依赖

```
bcrypt==4.1.*
pyjwt==2.8.*
```

### 3.3 JWT 配置

在 `config.yaml` 中新增：

```yaml
auth:
  secret_key: "change-me-to-a-random-secret"   # 生产环境必须通过环境变量覆盖
  algorithm: "HS256"
  expire_minutes: 1440                         # 24 小时
```

环境变量覆盖：`AUTH_SECRET_KEY`

### 3.4 新增模块

```
backend/app/auth/
  __init__.py          # 导出
  models.py            # Pydantic models (LoginRequest, RegisterRequest, TokenResponse, UserInfo)
  service.py           # 核心业务逻辑 (create_user, authenticate_user, get_user_by_id)
  middleware.py         # FastAPI 依赖 (get_current_user, require_admin)
  router.py            # 认证路由 (/api/auth/*)
```

### 3.5 API 端点

#### 认证 API（公开）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/auth/register` | 注册新用户 |
| `POST` | `/api/auth/login` | 登录，返回 JWT token |
| `GET` | `/api/auth/me` | 获取当前用户信息（需 Bearer token） |

**POST /api/auth/register**

```json
// Request
{ "username": "alice", "password": "securePass123" }

// Response 201
{ "id": "uuid", "username": "alice", "role": "user", "created_at": "..." }
```

逻辑：
1. 检查 `users` 表是否有记录
   - 无记录 → 该用户为**管理员**（`role = 'admin'`）
   - 有记录 → 该用户为普通用户（`role = 'user'`）
2. 用户名唯一校验
3. bcrypt 哈希密码
4. 返回用户信息（不含密码）

**POST /api/auth/login**

```json
// Request
{ "username": "alice", "password": "securePass123" }

// Response 200
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": { "id": "uuid", "username": "alice", "role": "user" }
}
```

**GET /api/auth/me**

```json
// Header: Authorization: Bearer <token>
// Response 200
{ "id": "uuid", "username": "alice", "role": "user", "created_at": "..." }
```

#### 管理员 API（需 admin 权限）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/admin/users` | 获取所有用户列表 |
| `PATCH` | `/api/admin/users/{id}` | 修改用户角色/启用状态 |
| `DELETE` | `/api/admin/users/{id}` | 删除用户 |
| `GET` | `/api/admin/users/{id}/databases` | 获取用户可访问的数据库列表 |
| `PUT` | `/api/admin/users/{id}/databases` | 设置用户可访问的数据库列表 |

**PUT /api/admin/users/{id}/databases**

```json
// Request
{ "database_ids": ["db1", "db2", "db3"] }

// Response 200
{ "database_ids": ["db1", "db2", "db3"] }
```

逻辑：先删除 `user_databases` 中该用户的所有记录，再批量插入新的。

#### 现有 API 修改

所有现有 API 需要增加 `user_id` 参数（从 JWT 中提取）：

| 端点 | 改动 |
|------|------|
| `POST /api/chat` | 添加 `current_user: User = Depends(get_current_user)`，传入 `user_id` |
| `POST /api/chat/stream` | 同上 |
| `GET /api/sessions` | 按 `user_id` 过滤 `WHERE user_id = ?` |
| `GET /api/sessions/{id}/messages` | 校验 session 属于当前用户 |
| `PATCH /api/sessions/{id}` | 校验归属 |
| `DELETE /api/sessions/{id}` | 校验归属 |
| `POST /api/sessions/clear` | 仅清除当前用户的会话 |
| `GET /api/database` | 管理员看到所有数据库，普通用户只看到被授权的 |

### 3.6 认证中间件

```python
# auth/middleware.py

async def get_current_user(
    authorization: str = Header(None),
    db: sqlite3.Connection = Depends(get_db)
) -> User:
    """从 JWT 中提取并验证当前用户。"""
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, '未登录')
    token = authorization.split(' ')[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = get_user_by_id(db, payload['sub'])
        if not user or not user.is_active:
            raise HTTPException(401, '用户不存在或已禁用')
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, '登录已过期，请重新登录')
    except jwt.InvalidTokenError:
        raise HTTPException(401, '无效的登录凭证')


def require_admin(user: User = Depends(get_current_user)) -> User:
    """要求当前用户为管理员。"""
    if user.role != 'admin':
        raise HTTPException(403, '需要管理员权限')
    return user
```

---

## 4. 前端设计

### 4.1 新增/修改文件

```
frontend/src/
  pages/
    LoginPage.tsx          # 登录页面
    RegisterPage.tsx       # 注册页面
  components/
    UserManagePanel.tsx    # 用户管理面板（管理员）
    DbAccessControl.tsx    # 数据库权限分配组件
  hooks/
    useAuth.ts             # 认证状态管理 hook
  store/
    authStore.ts           # Zustand auth store
  api/
    index.ts               # 新增 auth & admin API 方法
```

### 4.2 路由设计

目前系统没有 router 库，采用条件渲染。修改 `App.tsx`：

```
未登录状态 → 渲染 LoginPage（或 RegisterPage）
已登录状态 → 渲染主界面（当前 App 内容）
管理员 → 在主界面侧边栏添加「用户管理」入口
```

状态流转：

```
                 ┌─────────────┐
                 │   LoginPage  │ ←──── 首次访问 / Token 过期
                 └──────┬──────┘
                        │ 登录成功
                        ▼
                 ┌─────────────┐
          ┌──────│   App 主界面  │──────┐
          │      └─────────────┘      │
          │ 点击注册                  │ 退出登录
          ▼                           ▼
   ┌──────────────┐           ┌─────────────┐
   │ RegisterPage  │           │   LoginPage  │
   └──────┬───────┘           └─────────────┘
          │ 注册成功 → 自动登录
          ▼
   ┌─────────────┐
   │  App 主界面  │
   └─────────────┘
```

### 4.3 认证状态管理 (authStore)

```typescript
interface AuthState {
  user: UserInfo | null
  token: string | null
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  register: (username: string, password: string) => Promise<void>
  logout: () => void
  checkAuth: () => Promise<void>   // 启动时检查 localStorage token
}
```

- `token` 持久化到 `localStorage`
- 每次 API 请求自动在 Header 中附加 `Authorization: Bearer <token>`
- `checkAuth()` 在 App 启动时调用，验证 token 是否有效

### 4.4 页面设计

#### LoginPage

- 简洁的居中卡片布局
- 用户名 + 密码输入框
- 登录按钮 + "没有账号？去注册" 链接
- 登录成功后跳转到主界面

#### RegisterPage

- 与登录页风格统一
- 用户名 + 密码 + 确认密码
- 注册按钮 + "已有账号？去登录" 链接
- 注册成功后自动登录并跳转到主界面

#### UserManagePanel（管理员）

作为侧边栏的一个面板或独立页面：

- 用户列表（表格）：用户名、角色、创建时间、操作按钮
- 操作为每一行：编辑角色、分配数据库、删除用户
- 分配数据库：弹窗显示所有数据库，复选框选择，保存

#### DbAccessControl（组件）

- 弹窗形式
- 显示所有已注册数据库列表
- 每行一个复选框，标记当前用户是否有权限
- "全选 / 取消全选" 按钮
- 保存按钮

### 4.5 API Client 修改

在 `api/index.ts` 中新增：

```typescript
// ===== 认证 =====
login(username: string, password: string): Promise<LoginResponse>
register(username: string, password: string): Promise<UserInfo>
getMe(): Promise<UserInfo>

// ===== 管理（管理员） =====
getUsers(): Promise<UserInfo[]>
updateUser(id: string, data: Partial<UserInfo>): Promise<UserInfo>
deleteUser(id: string): Promise<void>
getUserDatabases(userId: string): Promise<string[]>
setUserDatabases(userId: string, dbIds: string[]): Promise<string[]>
```

同时，现有的 `api` 模块需要增加一个统一的请求拦截器，自动附加 JWT token：

```typescript
// 现有 request 函数增加 Authorization header
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('auth_token')
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  // ... 其余逻辑不变
}
```

### 4.6 会话隔离

- `GET /api/sessions` 后端已按 `user_id` 过滤，前端无需额外改动
- `handleSendMessage` 中使用的 `activeSessionId` 和 `activeDbId` 本来就是按用户隔离的

---

## 5. 数据库变更

### 5.1 数据迁移脚本

创建 `backend/app/persistence/migration_002_users.py`：

```python
def migrate_users(conn: sqlite3.Connection):
    """用户管理系统的数据库迁移。"""
    cursor = conn.cursor()

    # 创建 users 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id          TEXT PRIMARY KEY,
            username    TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role        TEXT NOT NULL DEFAULT 'user'
                         CHECK(role IN ('admin', 'user')),
            is_active   INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    ''')

    # 创建 user_databases 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_databases (
            user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            database_id TEXT NOT NULL REFERENCES databases(id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, database_id)
        )
    ''')

    # 检查 sessions 表是否已有 user_id 列
    columns = [col[1] for col in cursor.execute('PRAGMA table_info(sessions)').fetchall()]
    if 'user_id' not in columns:
        cursor.execute('ALTER TABLE sessions ADD COLUMN user_id TEXT REFERENCES users(id)')

    conn.commit()
```

### 5.2 首次用户逻辑

在 `auth/service.py` 中：

```python
def register_user(conn, username: str, password: str) -> User:
    """注册新用户。首个注册用户自动成为管理员。"""
    cursor = conn.cursor()
    
    # 检查用户名是否已存在
    existing = cursor.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    if existing:
        raise ValueError('用户名已存在')
    
    # 判断是否为第一个用户
    user_count = cursor.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    role = 'admin' if user_count == 0 else 'user'
    
    # 创建用户
    user_id = str(uuid.uuid4())
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    now = datetime.utcnow().isoformat()
    
    cursor.execute(
        'INSERT INTO users (id, username, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
        (user_id, username, password_hash, role, now, now)
    )
    conn.commit()
    
    return User(id=user_id, username=username, role=role, created_at=now)
```

---

## 6. 安全注意事项

1. **密码要求**：至少 6 位，前端+后端双重校验
2. **JWT 密钥**：生产环境通过 `AUTH_SECRET_KEY` 环境变量设置，不写入代码仓库
3. **HTTPS**：生产环境部署必须使用 HTTPS，防止 token 被截获
4. **速率限制**：登录接口建议增加速率限制（可选）
5. **Token 刷新**：暂不实现 refresh token 机制，24 小时过期后需重新登录
6. **前端 Token 存储**：使用 `localStorage`，注意 XSS 防护

---

## 7. 实施步骤

### Phase 1: 后端基础设施
1. 安装 `bcrypt`、`pyjwt` 依赖
2. 创建 `auth/` 模块（models、service、middleware、router）
3. 创建 `persistence/migration_002_users.py` 迁移脚本
4. 在 `main.py` 中注册 auth router
5. 在 `init_sqlite()` 中调用迁移脚本

### Phase 2: 后端 API 改造
1. 为现有 API 添加 `get_current_user` 依赖
2. 修改 sessions 查询按 `user_id` 过滤
3. 修改 databases 查询按权限过滤
4. 添加管理员 API 端点

### Phase 3: 前端认证
1. 创建 `authStore`（Zustand）
2. 创建 `LoginPage`、`RegisterPage`
3. 修改 `App.tsx` 根据登录状态渲染
4. 修改 `api/index.ts` 添加 JWT 拦截

### Phase 4: 前端管理功能
1. 创建 `UserManagePanel` 组件
2. 创建 `DbAccessControl` 组件
3. 在侧边栏添加管理入口（仅管理员可见）
4. 调试和联调

### Phase 5: 测试与收尾
1. 后端接口测试
2. 前端流程测试
3. 权限边界测试
4. 编写 changes log

---

## 8. 影响范围分析

| 模块 | 改动量 | 风险 |
|------|--------|------|
| 后端数据层 | 新增 2 张表 + 1 个 ALTER | 低 |
| 后端路由 | 新增 auth + admin 路由，修改现有路由参数 | 中 |
| 后端聊天逻辑 | 传递 user_id 到 session | 低 |
| 前端状态管理 | 新增 authStore | 低 |
| 前端页面 | 新增 LoginPage/RegisterPage | 低 |
| 前端组件 | 新增 UserManagePanel/DbAccessControl | 低 |
| 前端 API 层 | 新增方法 + 统一 Auth header | 低 |
| 现有功能 | 会话隔离、数据库权限过滤 | 中（需测试覆盖） |
