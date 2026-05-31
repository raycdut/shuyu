"""Schema Description Agent — generates Chinese semantic descriptions for database tables and columns.

This agent reads imported table/column metadata from SQLite, sends batches to LLM,
and saves the generated descriptions back to the database.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .. import state
from ..client import call_llm
from ..persistence.schema import load_full_schema, save_descriptions

logger = logging.getLogger("shuyu.agent")

SYSTEM_PROMPT = """你是一个数据分析专家，负责为数据库表和字段添加中文语义描述。
你的描述能让数据分析师快速理解每个表和字段的业务含义。

## 输出要求
返回 JSON 对象，包含一个 "tables" 数组，每个元素包含：
- table_name: 表名
- table_description: 表的中文业务描述（20-50字）
- columns: 列描述数组
  - column_name: 列名
  - column_description: 列的中文业务描述（10-30字）

## 描述规范
1. 描述要有实际业务含义，不要只是直译英文名
2. 如果字段名包含 id 且可能是外键（如 customer_id），要说明关联含义
3. 主键字段在描述中标注
4. 时间字段说明含义（如创建时间、更新时间）
5. 金额字段说明类型（如单价、总价）
6. 布尔/状态字段说明各取值含义
"""


def _build_table_block(table: dict) -> str:
    """Build a text block for a single table to include in the prompt."""
    lines = [f"表名: {table['table_name']}"]
    if table.get("description"):
        lines.append(f"现有描述: {table['description']}")
    lines.append("字段:")
    for col in table.get("columns", []):
        pk = " (主键)" if col.get("is_primary_key") else ""
        nullable = "" if col.get("is_nullable", True) else " (非空)"
        sample = ""
        if col.get("sample_values"):
            vals = col["sample_values"]
            if len(vals) > 3:
                vals = vals[:3]
            sample = f" 示例值: {', '.join(str(v) for v in vals)}"
        lines.append(f"  - {col['column_name']}: {col['data_type']}{pk}{nullable}{sample}")
    return "\n".join(lines)


def _build_user_prompt(database_name: str, tables: list[dict]) -> str:
    """Build the user prompt for a batch of tables."""
    parts = [f"请为以下数据库表和字段添加中文描述：\n\n数据库名称: {database_name}\n"]
    for t in tables:
        parts.append(_build_table_block(t))
        parts.append("")
    parts.append("请分析表名和字段名，给出合理的中文业务描述。")
    return "\n".join(parts)


def _parse_llm_response(response: Any) -> list[dict]:
    """Parse the LLM response and extract descriptions."""
    try:
        content = response.choices[0].message.content
        if not content:
            logger.warning("Empty LLM response")
            return []

        # Try to extract JSON from markdown code blocks
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        parsed = json.loads(content)
        tables = parsed.get("tables", parsed if isinstance(parsed, list) else [])
        if isinstance(tables, dict):
            tables = [tables]
        return tables
    except (json.JSONDecodeError, AttributeError, KeyError) as e:
        logger.error(f"Failed to parse LLM response: {e}")
        logger.debug(f"Raw response: {response}")
        return []


async def generate_descriptions(
    database_id: str,
    table_ids: list[str] | None = None,
    language: str = "zh",
    force: bool = False,
) -> dict:
    """Generate Chinese descriptions for tables and columns.

    Args:
        database_id: Target database ID.
        table_ids: Specific table IDs to describe (None = all).
        language: Output language ("zh" or "en").
        force: If True, regenerate descriptions even if they already exist.

    Returns:
        Dict with tables_count and columns_count.
    """
    tables = load_full_schema(database_id)
    if not tables:
        logger.info(f"No imported tables found for database {database_id}")
        return {"tables_count": 0, "columns_count": 0}

    # Filter specific tables if requested
    if table_ids:
        tables = [t for t in tables if t["id"] in table_ids]

    # Skip tables that already have descriptions (unless forced)
    if not force:
        tables_to_process = []
        for t in tables:
            has_description = bool(t.get("description"))
            all_cols_described = all(
                bool(c.get("description")) for c in t.get("columns", [])
            )
            if not has_description or not all_cols_described:
                tables_to_process.append(t)
        tables = tables_to_process

    if not tables:
        logger.info("All tables already have descriptions")
        return {"tables_count": 0, "columns_count": 0}

    # Get database name for context
    db_name = database_id
    for db in state._db_connections:
        if db["id"] == database_id:
            db_name = db["name"]
            break

    # Process in batches
    BATCH_SIZE = 8
    all_descriptions = []
    total_tables = 0

    for i in range(0, len(tables), BATCH_SIZE):
        batch = tables[i : i + BATCH_SIZE]
        logger.info(f"Generating descriptions for batch {i // BATCH_SIZE + 1} ({len(batch)} tables)")

        prompt = _build_user_prompt(db_name, batch)
        try:
            response = await call_llm(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            descriptions = _parse_llm_response(response)
            all_descriptions.extend(descriptions)
            total_tables += len(descriptions)
            logger.info(f"Batch complete: {len(descriptions)} tables described")
        except Exception as e:
            logger.error(f"Failed to generate descriptions for batch: {e}")

    # Save all descriptions to database
    if all_descriptions:
        updated = save_descriptions(database_id, all_descriptions)
        logger.info(f"Saved descriptions for {updated} tables")
    else:
        logger.warning("No descriptions were generated")

    columns_count = sum(len(d.get("columns", [])) for d in all_descriptions)
    return {"tables_count": total_tables, "columns_count": columns_count}
