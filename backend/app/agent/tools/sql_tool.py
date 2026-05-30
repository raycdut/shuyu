"""SQL Tool — generates and executes SQL queries against the connected database."""

from __future__ import annotations

import json
import logging
from typing import Any

from ...db.base import DatabaseConnector

logger = logging.getLogger("shuyu.sql")


async def handle_sql_query(
    question: str,
    connector: DatabaseConnector,
    schema_prompt: str,
    call_llm_func: Any,
    max_rows: int = 1000,
) -> str:
    """Handle a natural language query by generating and executing SQL.

    This is NOT a registered tool itself — it's the core logic invoked by
    the agent loop when the LLM decides to call the 'query_database' tool.
    """
    # Build prompt for SQL generation
    system_prompt = f"""你是一个 SQL 专家。根据用户的问题和数据库结构，生成正确的 SQL 查询。

数据库结构：
{schema_prompt}

规则：
1. 只生成 SELECT 查询
2. 只使用数据库中存在的表和字段
3. 使用中文别名（AS）让结果可读
4. 如果问题不明确，选择最合理的解释
5. 如果无法生成 SQL，回复 "UNABLE: 原因"

直接输出 SQL，不要解释。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"问题：{question}\n\n请生成 SQL："},
    ]

    sql_response = await call_llm_func(messages)
    sql = sql_response.strip()
    logger.info(f"SQL generated ({len(sql)} chars): {sql.replace(chr(10), ' ')}")

    # Track SQL for frontend display
    from ... import state
    qn = len(state._last_sql_queries) + 1
    if state._last_sql_queries is not None:
        state._last_sql_queries.append(sql)

    # Clean up SQL from possible markdown fences
    if sql.startswith("```"):
        sql = sql.split("\n", 1)[1] if "\n" in sql else sql
        sql = sql.rsplit("```", 1)[0] if "```" in sql else sql

    if sql.upper().startswith("UNABLE"):
        logger.warning(f"SQL generation failed: {sql}")
        return f"无法生成 SQL：{sql}"

    # Safety: enforce read-only
    sql_upper = sql.strip().upper()
    if not sql_upper.startswith("SELECT"):
        logger.warning(f"Blocked non-SELECT SQL: {sql[:100]}")
        return "⚠️ 只允许 SELECT 查询。"
    for keyword in ("DROP", "ALTER", "DELETE", "INSERT", "UPDATE", "CREATE", "TRUNCATE", "EXEC", "EXECUTE"):
        if keyword in sql_upper:
            logger.warning(f"Blocked dangerous SQL: {sql[:100]}")
            return f"⚠️ 查询包含被禁止的关键字 {keyword}。"

    # Execute
    try:
        logger.info("Executing SQL...")
        result = connector.execute(sql, max_rows=max_rows)
        logger.info(f"SQL done: {result.row_count} rows returned")
        result_text = result.to_text(max_rows=20)
        return f"[Q{qn}]\n{result_text}"
    except Exception as e:
        logger.error(f"SQL execution error: {e}")
        logger.debug(f"Failed SQL: {sql}")
        return f"SQL 执行失败：{e}\n\n生成的 SQL：\n{sql}"


async def handle_query_database(question: str) -> str:
    """Registered tool handler: wraps handle_sql_query with current state.

    Uses state._active_connector (set per-request in chat route).
    """
    from ... import state as _state
    from ...db.schema import build_schema_prompt as _build_schema
    from ...client import call_llm as _call_llm

    _logger = logging.getLogger("shuyu.main")
    _logger.info(f"SQL tool: processing question '{question[:80]}'")

    if _state._active_connector is None:
        return "⚠️ 没有选中的数据库，无法查询。请先在左侧选择一个数据库。"

    tables = _state._active_connector.get_schema()
    schema_text = _build_schema(tables)

    async def _call_llm_for_sql(msgs):
        resp = await _call_llm(msgs)
        return resp.choices[0].message.content

    return await handle_sql_query(
        question=question,
        connector=_state._active_connector,
        schema_prompt=schema_text,
        call_llm_func=_call_llm_for_sql,
        max_rows=_state.config.safety.max_rows,
    )


def create_query_database_tool(connector: DatabaseConnector, call_llm_func: Any, schema_prompt: str):
    """Create a 'query_database' tool for the registry."""

    async def handler(question: str) -> str:
        return await handle_sql_query(
            question=question,
            connector=connector,
            schema_prompt=schema_prompt,
            call_llm_func=call_llm_func,
        )

    return {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": "用自然语言查询数据库。输入你想问的问题，我会生成 SQL 并执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "关于数据的自然语言问题，如「上月销量最高的产品是什么」",
                    }
                },
                "required": ["question"],
            },
        },
    }
