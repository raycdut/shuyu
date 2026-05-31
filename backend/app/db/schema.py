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
            for c in t.get("columns", []):
                if c.get("description"):
                    col_descs[c["column_name"]] = c["description"]
            result[t["table_name"]] = {
                "description": t.get("description", ""),
                "columns": col_descs,
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
        col_descs = desc.get("columns", {})

        cols_text = []
        for c in (t.columns or []):
            col_desc = col_descs.get(c.name, c.comment or "")
            parts = [f"    - {c.name}: {c.data_type}"]
            if c.is_primary_key:
                parts.append(" (PK)")
            if col_desc:
                parts.append(f" — {col_desc}")
            cols_text.append("".join(parts))

        lines.append(f"表: {table_name}")
        if table_desc:
            lines.append(f"  描述: {table_desc}")
        if cols_text:
            lines.extend(cols_text)
    return "\n".join(lines)


def build_schema_light(tables, db_id: str | None = None) -> str:
    """Table names + column names + brief description — for agent planning."""
    if not tables:
        return "当前无可查数据"

    descriptions = _load_dynamic_descriptions(db_id) if db_id else {}

    # Fallback descriptions for well-known table names
    fallback = {
        "dim_customer": "客户信息（含 full_name 姓名）",
        "dim_product": "产品信息（名称、类别）",
        "dim_date": "日期维度",
        "dim_employee": "员工信息",
        "dim_territory": "销售区域",
        "dim_sales_person": "销售人员",
        "dim_vendor": "供应商",
        "dim_address_type": "地址类型",
        "dim_contact_type": "联系方式类型",
        "dim_currency": "币种",
        "dim_department": "部门",
        "dim_location": "仓库位置",
        "dim_sales_reason": "销售原因",
        "dim_ship_method": "配送方式",
        "dim_tax_rate": "税率",
        "dim_unit_measure": "度量单位",
        "fct_orders": "订单头（日期、客户、总金额）",
        "fct_order_details": "订单行明细（产品、数量、单价）",
        "fct_orders_with_reasons": "订单明细+退单原因（含产品、数量、金额、退单原因）",
        "fct_purchasing": "采购记录",
        "fct_shopping_cart": "购物车数据",
        "fct_inventory_transactions": "库存变动记录",
    }

    parts = ["可用表："]
    for t in tables:
        col_names = [c.name for c in (t.columns or [])]

        # Use dynamic description first, then fallback
        dynamic = descriptions.get(t.name, {})
        desc = dynamic.get("description", "") or fallback.get(t.name, "")

        suffix = f" — {desc}" if desc else ""
        parts.append(f"  {t.name}({', '.join(col_names[:8])}{'...' if len(col_names) > 8 else ''}){suffix}")
    return "\n".join(parts)
