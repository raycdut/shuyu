# Docker + MySQL 部署改造方案与进度

> 分支: `docker-mysql-deploy`

## 目标

提供一个**一键部署脚本**，用户只需执行 `./scripts/setup.sh` 或 `make setup`，即可完成：
- Docker 启动 Frontend + Backend + MySQL 服务
- MySQL 作为生产环境 ConfigDB（替代 SQLite）
- 本地开发仍使用 SQLite，无需改动

---

## 改造方案

### 架构变更

```
改造前：                         改造后：
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────────────┐
│ Frontend │───▶│ Backend  │    │ Frontend │───▶│     Backend      │
│ Nginx:80 │    │ FastAPI  │    │ Nginx:80 │    │ FastAPI+SQLAlchemy│
└──────────┘    │ SQLite   │    └──────────┘    ├──────────────────┤
                │ (config) │                    │ ConfigDB:        │
                │ DuckDB   │                    │  ├─ dev: SQLite   │
                │ (analytics)│                   │  └─ prod: MySQL  │
                └──────────┘                    │ Analytics:       │
                                                │  DuckDB/MySQL/PG │
                                                └──────────────────┘
```

### 技术选型

| 组件 | 选择 | 原因 |
|------|------|------|
| ORM | SQLAlchemy 2.0 | 用户选择，自动处理 SQLite/MySQL 方言差异 |
| MySQL驱动 | PyMySQL | 已存在于 `requirements.txt` |
| ConfigDB 连接 | `CONFIGDB_URL` 环境变量 | 无缝切换 SQLite ↔ MySQL |

---

## 第一阶段：Docker 基础设施（已完成 ✅）

| 文件 | 状态 | 说明 |
|------|------|------|
| `.env.example` | ✅ 新建 | LLM_API_KEY / MySQL 密码 / AUTH_SECRET_KEY 等模板 |
| `docker-compose.yml` | ✅ 重写 | 加 MySQL 服务 + 健康检查 + `.env` 引用 + 自定义网络 |
| `Makefile` | ✅ 新建 | `make up` / `make down` / `make setup` 等快捷命令 |
| `scripts/setup.sh` | ✅ 新建 | 一键部署脚本（环境检查 → 配置 → 启动 → 等待就绪） |
| `backend/Dockerfile` | ✅ 修改 | 加 MySQL client + healthcheck |
| `backend/requirements.txt` | ✅ 修改 | 加 `sqlalchemy>=2.0.0` |
| `frontend/Dockerfile` | ✅ 修改 | 复制自定义 nginx.conf |
| `frontend/nginx.conf` | ✅ 新建 | API 反向代理 + SPA fallback + 静态资源缓存 |

---

## 第二阶段：SQLAlchemy ORM 重构 ConfigDB

### 新增文件

| 文件 | 状态 | 说明 |
|------|------|------|
| `configdb/__init__.py` | ✅ 新建 | `init_configdb()` 工厂函数 + 默认 Prompt 定义 + 种子数据 |
| `configdb/base.py` | ✅ 新建 | `create_configdb_engine()` + `get_session()` + `scoped_session()` |
| `configdb/models/__init__.py` | ✅ 新建 | Declarative Base + 导出所有模型 |
| `configdb/models/user.py` | ✅ 新建 | User, UserDatabase ORM 模型 |
| `configdb/models/session.py` | ✅ 新建 | Session, Message ORM 模型 |
| `configdb/models/database.py` | ✅ 新建 | DatabaseConnection ORM 模型 |
| `configdb/models/config.py` | ✅ 新建 | SystemConfig, UserConfig, ConfigChangelog, Setting, LlmProvider |
| `configdb/models/prompt.py` | ✅ 新建 | Prompt ORM 模型 |
| `configdb/models/schema.py` | ✅ 新建 | ImportedTable, ImportedColumn ORM 模型 |
| `configdb/models/token.py` | ✅ 新建 | TokenUsage ORM 模型 |

### 改造文件

| 文件 | 状态 | 说明 |
|------|------|------|
| `state.py` | ✅ 修改 | 加 `_configdb_engine` + `_configdb_session_factory`；保留 `_sqlite` 向后兼容 |
| `main.py` | ✅ 修改 | `init_sqlite()` → `init_configdb()`；Prompt 加载改用 scoped_session |
| `persistence/__init__.py` | ✅ 修改 | 改为从 configdb 重新导出的兼容层 |
| `persistence/config.py` | ✅ 修改 | SQLite 裸 SQL → scoped_session + ORM |
| `persistence/database.py` | ✅ 修改 | SQLite 裸 SQL → scoped_session + ORM |
| `persistence/schema.py` | ✅ 修改 | SQLite 裸 SQL → scoped_session + ORM |
| `persistence/token.py` | ✅ 修改 | SQLite 裸 SQL → scoped_session + ORM |
| `auth/service.py` | ✅ 修改 | `state._sqlite.execute()` → scoped_session + ORM |
| `admin_config/service.py` | ✅ 修改 | `state._sqlite.execute()` → scoped_session + ORM |
| `session/manager.py` | ✅ 修改 | `SessionManager(sqlite_conn=...)` → `SessionManager()` + scoped_session |
| `routes/config.py` | ✅ 修改 | Prompt 管理改用 scoped_session + ORM |
| `routes/admin_stats.py` | ✅ 修改 | 统计查询改用 scoped_session + ORM |

### 测试适配

| 文件 | 状态 | 说明 |
|------|------|------|
| `tests/conftest.py` | ✅ 新建 | 自动初始化内存 SQLite ConfigDB |
| `test_admin_config_service.py` | ✅ 保留 | `setup_db` 仅调 `init_auth_config()` + 设 LLM 配置 |
| `test_prompt_api.py` | 🔄 已有 | 使用 `state._sqlite`，由 conftest 提供 |
| `test_routes_chat.py` | ✅ 修复 | mock `init_sqlite` → `init_configdb` |
| `test_routes_config.py` | 🔄 已有 | 使用 `state._sqlite`，由 conftest 提供 |
| `test_admin_stats_api.py` | ✅ 修复 | mock `init_sqlite` → `init_configdb` |
| `test_persistence_schema.py` | 🔄 待清理 | 有冗余的 `setup_db` fixture |
| `test_persistence_token.py` | 🔄 待清理 | 有冗余的 `setup_db` fixture |

### 测试运行状态

```
255 passed in 31.77s ✅ 全部通过
```

| 测试文件 | 改造方式 | 状态 |
|---------|---------|------|
| `tests/conftest.py` | 新建：临时文件 SQLite，同时维护 ORM 引擎和 raw 连接 | ✅ |
| `test_admin_config_service.py` | 保留简单 fixture，移除 DB 重初始化 | ✅ |
| `test_routes_chat.py` | mock `init_sqlite` → `init_configdb` | ✅ |
| `test_admin_stats_api.py` | `seed_test_data()` 改用 ORM + scoped_session | ✅ |
| `test_routes_config.py` | 所有 DB 操作用 ORM，唯一分类名避免种子冲突 | ✅ |
| `test_prompt_api.py` | 所有 DB 操作用 ORM，迁移测试从 `app.configdb` 导入 | ✅ |
| `test_persistence_schema.py` | 所有 DB 操作用 ORM，setup_db 改用 scoped_session | ✅ |
| `test_persistence_token.py` | DB 验证改用 ORM 查询 | ✅ |

### 全量后端测试

```bash
cd backend && python3 -m pytest tests/ -q
255 passed in 31.77s
```

---

## 用户使用流程

### 生产部署（带 MySQL）

```bash
git clone <repo>
cd agentic-data-analyst
cp .env.example .env
# 编辑 .env: 设置 LLM_API_KEY 和 AUTH_SECRET_KEY
./scripts/setup.sh
# 浏览器打开 http://localhost:3000
```

### 本地开发（SQLite，不变）

```bash
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload

cd frontend && npm install && npm run dev
```

---

## 待办项

- [x] 修复 `test_admin_stats_api.py` 中的 mock 问题
- [x] 清理 `test_persistence_schema.py` / `test_persistence_token.py` 中的冗余 `setup_db` fixture
- [x] 运行全量测试确保全部通过 — **255 passed ✅**
- [ ] 在 Docker 环境中端到端验证 MySQL ConfigDB
- [ ] 更新 CHANGELOG.md
