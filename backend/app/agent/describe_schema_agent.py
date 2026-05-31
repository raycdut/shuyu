"""Schema Description Agent — generates/optimizes bilingual (CN/EN) descriptions.

This agent reads imported table/column metadata from SQLite, sends batches to LLM,
and saves the generated descriptions back to the database.

Key behaviors:
- Generates both Chinese and English descriptions
- If existing descriptions exist, optimizes/improves them rather than replacing
- Can target specific tables via table_ids parameter
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .. import state
from ..client import call_llm
from ..persistence.schema import load_full_schema, save_descriptions

logger = logging.getLogger("shuyu.agent")

DEFAULT_SCHEMA_DESCRIBE_PROMPT = """你是一个数据分析专家，负责为数据库表和字段生成或优化中英文双语语义描述。

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


def _build_table_block(table: dict) -> str:
    """Build a text block for a single table, including existing descriptions."""
    lines = [f"表名: {table['table_name']}"]
    if table.get("description"):
        lines.append(f"现有中文描述: {table['description']}")
    if table.get("description_en"):
        lines.append(f"Existing EN description: {table['description_en']}")
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
        existing_cn = f" 现有中文描述: {col['description']}" if col.get("description") else ""
        existing_en = f" 现有EN描述: {col['description_en']}" if col.get("description_en") else ""
        lines.append(f"  - {col['column_name']}: {col['data_type']}{pk}{nullable}{sample}{existing_cn}{existing_en}")
    return "\n".join(lines)


def _build_user_prompt(database_name: str, tables: list[dict]) -> str:
    """Build the user prompt for a batch of tables."""
    parts = [f"请为以下数据库表和字段生成或优化中英文双语描述：\n\n数据库名称: {database_name}\n"]
    for t in tables:
        parts.append(_build_table_block(t))
        parts.append("")
    parts.append("请分析表名和字段名，生成或优化合理的中英文业务描述。已有描述的请优化完善，不要丢失原有信息。")
    return "\n".join(parts)


def _parse_llm_response(response: Any) -> list[dict]:
    """Parse the LLM response and extract descriptions."""
    try:
        content = response.choices[0].message.content
        if not content:
            logger.warning("Empty LLM response")
            return []

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
    """Generate or optimize bilingual descriptions for tables and columns.

    Args:
        database_id: Target database ID.
        table_ids: Specific table IDs to describe (None = all).
        language: Output language ("zh" or "en").
        force: If True, process tables even if they already have descriptions.

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

    if not tables:
        logger.info("No matching tables found")
        return {"tables_count": 0, "columns_count": 0}

    # Get database name for context
    db_name = database_id
    for db in state._db_connections:
        if db["id"] == database_id:
            db_name = db["name"]
            break

    # Process — always process when table_ids is explicitly provided
    all_descriptions = []
    total_tables = 0
    BATCH_SIZE = 8

    for i in range(0, len(tables), BATCH_SIZE):
        batch = tables[i : i + BATCH_SIZE]
        logger.info(f"Processing batch {i // BATCH_SIZE + 1} ({len(batch)} tables)")

        system_prompt = state.schema_describe_prompt or DEFAULT_SCHEMA_DESCRIBE_PROMPT
        prompt = _build_user_prompt(db_name, batch)
        try:
            response = await call_llm(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            descriptions = _parse_llm_response(response)
            all_descriptions.extend(descriptions)
            total_tables += len(descriptions)
            logger.info(f"Batch complete: {len(descriptions)} tables processed")
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
