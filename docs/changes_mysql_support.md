# MySQL 数据库支持

## 变更概要

为项目添加 MySQL 数据库连接支持，使用户可以连接本地或远程 MySQL 数据库进行数据分析。

## 变更文件

### 后端新增

- **backend/app/db/mysql.py** — MySQL 连接器，实现 `DatabaseConnector` 抽象接口
  - `MySQLConnector.connect()` — 通过 PyMySQL 建立连接
  - `MySQLConnector.get_schema()` — 从 `information_schema` 读取表结构和主键
  - `MySQLConnector.execute()` — 执行 SQL 查询，支持参数化查询和行数统计
  - `MySQLConnector.test_connection()` — 执行 SELECT 1 验证连接
  - 支持 `include_tables`/`exclude_tables` 过滤

### 后端修改

- **backend/requirements.txt** — 添加 `pymysql>=1.1.0`
- **backend/app/routes/database.py** — 支持 MySQL:
  - 新增 `_create_connector(entry)` 工厂函数
  - `GET /api/database/{db_id}/tables` — 支持 MySQL 表列表
  - `POST /api/database/test` — 支持 MySQL 连接测试
  - `POST /api/database/{db_id}/schema/import` — 支持 MySQL Schema 导入
  - 修复 `connect_database` 未保存 `password` 字段的问题
- **backend/app/routes/chat.py** — 支持 MySQL:
  - 新增 `_create_connector(db_entry)` 工厂函数
  - `POST /api/chat` 和 `POST /api/chat/stream` 改用工厂模式创建连接器

### 测试新增

- **backend/tests/test_db_mysql.py** — MySQL 连接器单元测试（11 tests）
  - 连接/断开连接测试
  - Schema 读取测试（含 include/exclude 过滤）
  - SQL 执行测试
  - 数据类型格式化测试

## 功能验证

| 功能 | 结果 |
|------|------|
| 测试 MySQL 连接 | ✅ 成功连接，发现 4 张表 |
| 添加 MySQL 数据库 | ✅ 成功注册 |
| 查看表列表 | ✅ 正确显示 4 张表的列和类型 |
| 导入 Schema | ✅ 成功导入 4 张表、30 个字段 |
| Schema 状态查询 | ✅ 正确显示导入状态 |
| Fast Mode Chat | ✅ 正确生成并执行 SQL |
| Quality Mode（深度分析）| ✅ 正确规划→执行→生成报告 |

## 测试结果

- 后端测试: **268 passed**（257 原有 + 11 新增）
- 前端测试: **126 passed**（无变化）
