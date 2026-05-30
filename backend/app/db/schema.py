"""Schema prompt builders — converts DuckDB schema to LLM-readable format."""

from __future__ import annotations


def build_schema_prompt(tables) -> str:
    """Full schema with columns — for SQL generation."""
    lines = ["以下是数据库中的表和字段：\n"]
    for t in tables:
        lines.append(t.to_prompt_block())
    return "\n".join(lines)


def build_schema_light(tables) -> str:
    """Table names + column names + brief description — for agent planning."""
    if not tables:
        return "当前无可查数据"

    descriptions = {
        "dim_customer": "客户信息（含 full_name 姓名）",
        "dim_product": "产品信息（名称、类别）",
        "dim_date": "日期维度",
        "dim_employee": "员工信息",
        "dim_territory": "销售区域",
        "dim_sales_person": "销售员信息（无姓名，需 JOIN int_sales_person_detail 或 int_person_detail）",
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
        "int_person_detail": "人员详细信息（含 full_name 姓名、职位）",
        "int_employee_overview": "员工总览（含姓名、部门、职位）",
        "int_sales_person_detail": "销售员详细信息（含姓名、区域、业绩）",
    }

    parts = ["可用表："]
    for t in tables:
        col_names = [c.name for c in t.columns]
        desc = descriptions.get(t.name, "")
        suffix = f" — {desc}" if desc else ""
        parts.append(f"  {t.name}({', '.join(col_names[:8])}{'...' if len(col_names) > 8 else ''}){suffix}")
    return "\n".join(parts)
