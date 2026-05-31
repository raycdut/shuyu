# 看板条目持久化 API 变更记录

**日期**: 2026-05-31

## 变更文件

### 1. `backend/app/persistence/__init__.py`

- 在 `init_sqlite()` 中新增 `_migrate_dashboard_tables()` 调用
- 新增 `_migrate_dashboard_tables()` 函数，用于创建 `dashboard_items` 表

**表结构**:
```sql
CREATE TABLE IF NOT EXISTS dashboard_items (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    query TEXT,
    chart_type TEXT DEFAULT 'table',
    chart_data TEXT,
    created_at REAL NOT NULL
);
```

### 2. `backend/app/routes/dashboard.py`（新文件）

新增 3 个 API 端点：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/dashboard/items` | 返回当前用户的看板条目列表（按创建时间降序） |
| POST | `/api/dashboard/items` | 添加条目，body: `{ title, query, chart_type, chart_data }` |
| DELETE | `/api/dashboard/items/{item_id}` | 删除指定条目（校验归属当前用户） |

**关键实现细节**:
- 所有接口通过 `Depends(get_current_user)` 验证 JWT 并获取用户信息
- `id` 使用 `uuid.uuid4()` 生成
- `created_at` 使用 `time.time()` 生成
- `chart_data` 字段存储 JSON 字符串，返回时反序列化
- POST 校验 `title` 必填非空

### 3. `backend/app/main.py`

- 在 import 中添加 `dashboard` 路由模块
- 在 router 注册中添加 `app.include_router(dashboard.router)`
