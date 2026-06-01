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
        if isinstance(parsed, list):
            tables = parsed
        else:
            tables = parsed.get("tables", [])
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

        system_prompt = state.schema_describe_prompt
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
