"""Tool handler — query_database: generates SQL via LLM, executes, returns results."""

from __future__ import annotations

import logging

from ... import state
from ...db.schema import build_schema_prompt
from .sql_tool import handle_sql_query

logger = logging.getLogger("shuyu.main")


async def handle_query_database(question: str) -> str:
    """Tool handler: query the database via natural language question.

    Uses state._active_connector (set per-request in chat route).
    """
    logger.info(f"SQL tool: processing question '{question[:80]}'")

    if state._active_connector is None:
        return "⚠️ 没有选中的数据库，无法查询。请先在左侧选择一个数据库。"

    tables = state._active_connector.get_schema()
    schema_text = build_schema_prompt(tables)

    async def _call_llm_for_sql(msgs):
        from ...client import call_llm
        resp = await call_llm(msgs)
        return resp.choices[0].message.content

    return await handle_sql_query(
        question=question,
        connector=state._active_connector,
        schema_prompt=schema_text,
        call_llm_func=_call_llm_for_sql,
        max_rows=state.config.safety.max_rows,
    )
