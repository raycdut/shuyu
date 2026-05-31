"""Schema prompt builders — converts DuckDB schema to LLM-readable format."""

from __future__ import annotations

from .. import state
from ..persistence.schema import load_full_schema


def _load_dynamic_descriptions(db_id: str | None = None) -> dict[str, dict]:
    """Load table and column descriptions from SQLite imported schema.

    Returns:
        dict mapping table_name -> {"description": str, "columns": {col_name: desc}}
    """
    if not db_id:
        return {}

    try:
        tables = load_full_schema(db_id)
        result = {}
        for t in tables:
            col_descs = {}
            col_descs_en = {}
            for c in t.get("columns", []):
                if c.get("description"):
                    col_descs[c["column_name"]] = c["description"]
                if c.get("description_en"):
                    col_descs_en[c["column_name"]] = c["description_en"]
            result[t["table_name"]] = {
                "description": t.get("description", ""),
                "description_en": t.get("description_en", ""),
                "columns": col_descs,
                "columns_en": col_descs_en,
            }
        return result
    except Exception:
        return {}


def build_schema_prompt(tables, db_id: str | None = None) -> str:
    """Full schema with columns — for SQL generation."""
    descriptions = _load_dynamic_descriptions(db_id) if db_id else {}

    lines = ["以下是数据库中的表和字段：\n"]
    for t in tables:
        table_name = t.name
        desc = descriptions.get(table_name, {})
        table_desc = desc.get("description", "")
        table_desc_en = desc.get("description_en", "")
        col_descs = desc.get("columns", {})
        col_descs_en = desc.get("columns_en", {})

        cols_text = []
        for c in (t.columns or []):
            col_desc = col_descs.get(c.name, c.comment or "")
            col_desc_en = col_descs_en.get(c.name, "")
            parts = [f"    - {c.name}: {c.data_type}"]
            if c.is_primary_key:
                parts.append(" (PK)")
            if col_desc:
                parts.append(f" — {col_desc}")
            if col_desc_en:
                parts.append(f" ({col_desc_en})")
            cols_text.append("".join(parts))

        lines.append(f"表: {table_name}")
        if table_desc:
            lines.append(f"  描述: {table_desc}")
        if table_desc_en:
            lines.append(f"  Description: {table_desc_en}")
        if cols_text:
            lines.extend(cols_text)
    return "\n".join(lines)


def build_schema_light(tables, db_id: str | None = None) -> str:
    """Table names + column names + brief description — for agent planning."""
    if not tables:
        return "当前无可查数据"

    descriptions = _load_dynamic_descriptions(db_id) if db_id else {}

    parts = ["可用表："]
    for t in tables:
        col_names = [c.name for c in (t.columns or [])]

        dynamic = descriptions.get(t.name, {})
        desc = dynamic.get("description", "")

        suffix = f" — {desc}" if desc else ""
        parts.append(f"  {t.name}({', '.join(col_names[:8])}{'...' if len(col_names) > 8 else ''}){suffix}")
    return "\n".join(parts)
