"""Persistence — SQLite init: DDL + seed data."""

from __future__ import annotations

import logging
from pathlib import Path

from .. import state

logger = logging.getLogger("shuyu.main")

DEFAULT_PROMPT = """<instructions>
  <role>data-analyst</role>
  <language>zh-CN</language>
  <workflow>
    <step>1. 理解用户的问题</step>
    <step>2. 必须调用 query_database 工具查询数据，不能凭表名猜测</step>
    <step>3. 根据查询结果回答用户</step>
    <step>4. 如果用户的问题不明确，主动澄清</step>
  </workflow>
  <rules>
    <rule>如果用户问「帮我分析一下」，主动问他们想分析什么维度和时间段</rule>
    <rule>使用中文回答</rule>
    <rule>回答简洁，突出关键数据</rule>
    <rule>如果工具返回了数据，直接根据数据回答，不要编造</rule>
  </rules>
</instructions>"""

SQL_GEN_PROMPT = """你是一个 SQL 专家。根据用户的问题和数据库结构，生成正确的 SQL 查询。

数据库结构：
{schema_prompt}

规则：
1. 只生成 SELECT 查询
2. 只使用数据库中存在的表和字段
3. 使用中文别名（AS）让结果可读
4. 如果问题不明确，选择最合理的解释
5. 如果无法生成 SQL，回复 "UNABLE: 原因"

直接输出 SQL，不要解释。"""

PLAN_PROMPT = """你是数据分析规划师。根据用户的提问和下方数据库结构，制定分析计划。

## 可用数据库
<database_schema>
请在下方 `<database>` 标签中查找可用的表和字段。
</database_schema>

## 核心规则（务必遵守）
1. **必须输出可执行的计划**：即使问题不明确，也要按最合理的理解制定计划，绝不能拒绝执行或输出空计划
2. **只使用上方 `<database>` 中列出的表和字段**，不要编造不存在的表或字段
3. **输出完整的、可直接执行的 SQL**
4. 如果一条 SQL 能解决问题，只写一步；确实需要多步时才拆分
5. 如果问题太模糊，按数据库中已有的表和字段做最合理的假设
6. 不要调用工具，只写计划

你必须输出符合下面结构的 JSON 对象，不要输出其他任何内容：

{
  "target": "一句话说明用户想分析什么",
  "steps": [
    {
      "purpose": "为什么查这个",
      "sql": "你的完整 SQL，可直接执行，如果没有 SQL 填 null"
    }
  ]
}"""

PLAN_REFLECT_PROMPT = """你是数据分析规划审核专家。请检查下面的分析计划是否合理。

检查清单：
1. 分析目标是否准确反映了用户的问题？
2. 每个分析步骤的 SQL 思路是否可行？（表名、关联字段、聚合方式是否合理）
3. 步骤顺序是否正确？（后面的步骤是否依赖前面的结果？）
4. 有没有多余的步骤？（一条 SQL 能解决的问题，不应该拆成多步）
5. 有没有遗漏重要的分析维度？

你必须输出符合下面结构的 JSON 对象，不要输出其他任何内容：

{
  "verdict": "合理 或 需要修改",
  "issues": ["如果有问题，逐条列出，没有填空数组"],
  "suggestions": ["如果有问题，给出具体的修改建议，没有填空数组"]
}"""

REPORT_REFLECT_PROMPT = """你是数据分析报告审核专家。请检查下面的分析报告。

检查清单：
1. 报告是否直接回应了用户的原始问题？
2. 报告中的数据是否有具体的数值支持（不应该是模糊描述）？
3. 有没有明显的遗漏或错误？
4. 是否有有趣的发现值得提及？

你必须输出符合下面结构的 JSON 对象，不要输出其他任何内容：

{
  "verdict": "通过 或 需要补充 或 计划错误",
  "issues": ["如果有问题，逐条列出，没有填空数组"],
  "suggestions": ["如果有问题，给出具体的修改建议，没有填空数组"],
  "needs_new_plan": true/false (如果是计划错误，导致现有数据无法修复报告，请设为 true)
}"""

SCHEMA_DESCRIBE_PROMPT = """你是一个数据分析专家，负责为数据库表和字段生成或优化中英文双语语义描述。

## 核心原则
1. 如果字段/表已有现有描述（existing description），你应当**优化和完善**它，而不是从零重写
2. 保留原意，修正不准确之处，补充遗漏的关键信息
3. 不要随意改动没有问题的内容
4. 描述要有实际业务含义，不要只是直译英文名

## 输出要求
返回 JSON 对象，包含一个 "tables" 数组，每个元素包含：
- table_name: 表名
- table_description: 表的中文业务描述（20-50字）
- table_description_en: 表的英文业务描述（20-50 words）
- columns: 列描述数组
  - column_name: 列名
  - column_description: 列的中文业务描述（10-30字）
  - column_description_en: 列的英文业务描述（10-30 words）

## 描述规范
1. 如果字段名包含 id 且可能是外键（如 customer_id），要说明关联含义
2. 主键字段在描述中标注
3. 时间字段说明含义（如创建时间、更新时间）
4. 金额字段说明类型（如单价、总价）
5. 布尔/状态字段说明各取值含义
"""


def init_sqlite() -> None:
    """Initialize SQLite database with schema and seed data."""
    import sqlite3
    import time

    logger.info(f"Initializing SQLite: {state.config.storage.path}")
    db_path = Path(state.config.storage.path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    state._sqlite = sqlite3.connect(str(db_path))
    state._sqlite.execute("PRAGMA journal_mode=WAL")
    state._sqlite.execute("PRAGMA busy_timeout=5000")

    state._sqlite.executescript("""
        CREATE TABLE IF NOT EXISTS llm_providers (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            provider   TEXT NOT NULL DEFAULT 'openai',
            model      TEXT NOT NULL DEFAULT 'gpt-4o',
            api_key    TEXT DEFAULT '',
            api_base   TEXT DEFAULT '',
            timeout    INTEGER DEFAULT 120,
            is_active  INTEGER DEFAULT 0,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        INSERT OR IGNORE INTO settings (key, value) VALUES ('safety_read_only', 'true');
        INSERT OR IGNORE INTO settings (key, value) VALUES ('safety_max_rows', '1000');
        CREATE TABLE IF NOT EXISTS databases (
            id                TEXT PRIMARY KEY,
            name              TEXT NOT NULL,
            type              TEXT NOT NULL DEFAULT 'duckdb',
            path              TEXT,
            connection_string TEXT,
            host              TEXT,
            port              INTEGER,
            username          TEXT,
            password          TEXT,
            db_name           TEXT,
            include_tables    TEXT,
            exclude_tables    TEXT,
            is_active         INTEGER DEFAULT 0,
            schema_status     TEXT DEFAULT 'pending'
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id         TEXT PRIMARY KEY,
            title      TEXT DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id),
            role      TEXT NOT NULL,
            content   TEXT NOT NULL DEFAULT '',
            tool_data TEXT,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS token_usage (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            model      TEXT NOT NULL,
            prompt     INTEGER NOT NULL DEFAULT 0,
            completion INTEGER NOT NULL DEFAULT 0,
            total      INTEGER NOT NULL DEFAULT 0,
            session_id TEXT,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS prompts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL DEFAULT 'default',
            content    TEXT NOT NULL,
            version    INTEGER NOT NULL DEFAULT 1,
            is_active  INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL
        );
    """)

    # ---- Prompt migration + seed ----
    _migrate_prompt_names()

    # Seed default prompts per category if any category missing
    prompt_seeds = {
        "system": DEFAULT_PROMPT,
        "sql_gen": SQL_GEN_PROMPT,
        "plan": PLAN_PROMPT,
        "plan_reflect": PLAN_REFLECT_PROMPT,
        "report_reflect": REPORT_REFLECT_PROMPT,
        "schema_describe": SCHEMA_DESCRIBE_PROMPT,
    }
    for name, content in prompt_seeds.items():
        exists = state._sqlite.execute(
            "SELECT COUNT(*) FROM prompts WHERE name = ?", (name,)
        ).fetchone()[0]
        if exists == 0:
            state._sqlite.execute(
                "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, 1, 1, ?)",
                (name, content, time.time()),
            )
    state._sqlite.commit()

    # Migrate existing tables: add timeout column if missing
    try:
        state._sqlite.execute("ALTER TABLE llm_providers ADD COLUMN timeout INTEGER DEFAULT 120")
    except Exception:
        pass

    # ---- Auth tables ----
    _migrate_auth_tables()
    from .migration_003_add_last_login import migrate_last_login
    migrate_last_login(state._sqlite)

    # ---- Schema tables ----
    _migrate_schema_tables()

    # ---- Config tables ----
    _migrate_config_tables()
    from .migration_004_expand_config_type import migrate_config_type
    migrate_config_type(state._sqlite)


def _migrate_auth_tables():
    """Create users + user_databases tables, add user_id to sessions."""
    state._sqlite.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            TEXT PRIMARY KEY,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'user'
                          CHECK(role IN ('admin', 'user')),
            is_active     INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS user_databases (
            user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            database_id TEXT NOT NULL REFERENCES databases(id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, database_id)
        );
    """)
    try:
        state._sqlite.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT REFERENCES users(id)")
    except Exception:
        pass
    # Migrate existing columns: add description_en column if missing
    try:
        state._sqlite.execute("ALTER TABLE imported_columns ADD COLUMN description_en TEXT DEFAULT ''")
    except Exception:
        pass
    state._sqlite.commit()


def _migrate_schema_tables():
    """Create imported_tables + imported_columns tables for schema management."""
    state._sqlite.executescript("""
        CREATE TABLE IF NOT EXISTS imported_tables (
            id              TEXT PRIMARY KEY,
            database_id     TEXT NOT NULL REFERENCES databases(id) ON DELETE CASCADE,
            table_name      TEXT NOT NULL,
            table_type      TEXT DEFAULT 'TABLE',
            row_count       INTEGER,
            description     TEXT DEFAULT '',
            description_en  TEXT DEFAULT '',
            raw_ddl         TEXT,
            created_at      REAL NOT NULL,
            updated_at      REAL NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_imported_tables_db_table ON imported_tables(database_id, table_name);
        CREATE TABLE IF NOT EXISTS imported_columns (
            id               TEXT PRIMARY KEY,
            table_id         TEXT NOT NULL REFERENCES imported_tables(id) ON DELETE CASCADE,
            column_name      TEXT NOT NULL,
            data_type        TEXT NOT NULL,
            is_nullable      INTEGER DEFAULT 1,
            is_primary_key   INTEGER DEFAULT 0,
            default_value    TEXT,
            ordinal_position INTEGER,
            description      TEXT DEFAULT '',
            description_en  TEXT DEFAULT '',
            sample_values    TEXT,
            created_at       REAL NOT NULL,
            updated_at       REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_imported_columns_table ON imported_columns(table_id);
    """)
    # Migrate existing databases: add schema_status column if missing
    try:
        state._sqlite.execute("ALTER TABLE databases ADD COLUMN schema_status TEXT DEFAULT 'pending'")
    except Exception:
        pass
    state._sqlite.commit()


def _migrate_config_tables():
    """Create system_config + user_configs + config_changelog tables."""
    state._sqlite.executescript("""
        CREATE TABLE IF NOT EXISTS system_config (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            config      TEXT NOT NULL DEFAULT '{}',
            updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_by  TEXT
        );
        CREATE TABLE IF NOT EXISTS user_configs (
            user_id     TEXT PRIMARY KEY,
            config      TEXT NOT NULL DEFAULT '{}',
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS config_changelog (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            config_type TEXT NOT NULL CHECK (config_type IN ('system', 'user', 'user_mgmt', 'database')),
            user_id     TEXT,
            changed_by  TEXT NOT NULL,
            summary     TEXT NOT NULL,
            diff        TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    state._sqlite.commit()
    _migrate_llm_providers_to_models()


def _migrate_llm_providers_to_models():
    """Migrate old llm_providers table data into system_config.models.

    Scenarios handled:
    1. system_config (id=1) does NOT exist → seed from llm_providers
    2. system_config exists but has no models field (only provider_pool) → merge llm_providers into models
    3. system_config already has models → skip (already migrated or configured via UI)
    """
    import json
    import uuid

    sql = state._sqlite
    if sql is None:
        return

    # Look for an active provider in the old table
    row = sql.execute(
        "SELECT provider, model, api_key, api_base, timeout, name FROM llm_providers WHERE is_active = 1 LIMIT 1"
    ).fetchone()
    if not row:
        return

    provider, model, api_key, api_base, timeout, name = row
    if not api_key:
        return

    logger.info(f"Found active llm_providers entry: {provider}/{model}, migrating to models format...")

    # Build a provider-friendly name if none exists
    if not name or name == provider:
        name = f"{provider.capitalize()} - {model}"

    # Build base URL map for common providers
    base_urls = {
        "openai": "https://api.openai.com/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "ollama": "http://localhost:11434/v1",
    }
    if not api_base and provider in base_urls:
        api_base = base_urls[provider]

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    models_entry = {
        "id": f"migrated-{provider}-{uuid.uuid4().hex[:6]}",
        "name": name,
        "provider": provider,
        "model": model or "gpt-4o",
        "api_key": api_key or "",
        "api_base": api_base or "",
        "timeout": timeout or 120,
        "enabled": True,
        "is_system_default": True,
    }

    # Check if system_config already exists
    existing = sql.execute("SELECT config FROM system_config WHERE id = 1").fetchone()
    if existing:
        try:
            existing_config = json.loads(existing[0])
        except (json.JSONDecodeError, TypeError):
            existing_config = {}

        # If it already has models, skip (already migrated or user configured)
        existing_models = existing_config.get("llm", {}).get("models", [])
        if existing_models:
            logger.info("system_config already has models, skipping migration")
            return

        # Merge the migrated model into existing config (preserving provider_pool etc.)
        existing_config.setdefault("llm", {})
        existing_config["llm"]["models"] = [models_entry]
        sql.execute(
            "UPDATE system_config SET config = ?, updated_at = ?, updated_by = ? WHERE id = 1",
            (json.dumps(existing_config), now, "system-migration"),
        )
        sql.commit()
        logger.info(f"Migration complete: merged {provider}/{model} into existing system_config")
    else:
        # system_config doesn't exist — seed it fresh
        config = {"llm": {"models": [models_entry]}}
        sql.execute(
            "INSERT INTO system_config (id, config, updated_at, updated_by) VALUES (1, ?, ?, ?)",
            (json.dumps(config), now, "system-migration"),
        )
        sql.commit()
        logger.info(f"Migration complete: system_config seeded with {provider}/{model}")


PROMPT_DEFAULTS: dict[str, str] = {
    "system": DEFAULT_PROMPT,
    "sql_gen": SQL_GEN_PROMPT,
    "plan": PLAN_PROMPT,
    "plan_reflect": PLAN_REFLECT_PROMPT,
    "report_reflect": REPORT_REFLECT_PROMPT,
    "schema_describe": SCHEMA_DESCRIBE_PROMPT,
}


def _get_default_prompt_content(category: str) -> str | None:
    """Get the hardcoded default prompt content for a category."""
    return PROMPT_DEFAULTS.get(category)


def _migrate_prompt_names():
    """Migrate old prompt name 'default' to 'system' for consistency."""
    sql = state._sqlite
    if sql is None:
        return
    row = sql.execute(
        "SELECT COUNT(*) FROM prompts WHERE name = 'default'"
    ).fetchone()
    if row and row[0] > 0:
        # Check if 'system' already exists to avoid conflicts
        existing = sql.execute(
            "SELECT COUNT(*) FROM prompts WHERE name = 'system'"
        ).fetchone()[0]
        if existing == 0:
            sql.execute("UPDATE prompts SET name = 'system' WHERE name = 'default'")
            sql.commit()
            logger.info("Migrated prompt name 'default' → 'system'")
        else:
            # 'system' already exists, de-duplicate by merging old default into system
            logger.info("Both 'default' and 'system' prompts exist, merging...")
            max_version = sql.execute(
                "SELECT MAX(version) FROM prompts WHERE name = 'system'"
            ).fetchone()[0] or 0
            default_rows = sql.execute(
                "SELECT content, version, is_active, created_at FROM prompts WHERE name = 'default' ORDER BY created_at ASC"
            ).fetchall()
            for content, version, is_active, created_at in default_rows:
                new_version = max_version + 1
                sql.execute(
                    "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, ?, ?, ?)",
                    ("system", content, new_version, is_active, created_at),
                )
                max_version = new_version
            sql.execute("DELETE FROM prompts WHERE name = 'default'")
            sql.commit()
            logger.info(f"Merged {len(default_rows)} 'default' prompts into 'system'")



