"""Chat route — POST /api/chat"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .. import state
from ..agent.tools.registry import Tool
from ..agent.tools.sql_tool import handle_sql_query
from ..db.duckdb import DuckDBConnector
from ..llm import build_schema_light, build_schema_prompt, call_llm
from ..models.schemas import ChatRequest, ChatResponse

logger = logging.getLogger("shuyu.main")

router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if state.agent_loop is None:
        raise HTTPException(503, "Agent not initialized")

    logger.info(f"POST /api/chat  session={req.session_id or 'new'}  db={req.db_id or 'none'}  msg={req.message[:50]}...")

    # Check API key
    if not state.config.llm.api_key and not os.environ.get("OPENAI_API_KEY"):
        logger.warning("Chat rejected: no LLM API key configured")
        return ChatResponse(
            reply="⚠️ 请先在右侧配置面板中设置 LLM API Key，然后再提问。",
            session_id=req.session_id or "",
            tool_calls=[],
        )

    session_id = req.session_id or str(uuid.uuid4())[:8]
    session = state.session_manager.get_or_create(session_id)

    # Auto-title
    if not session.metadata.get("title") and len(session.messages) == 0:
        title = req.message[:30] + ("…" if len(req.message) > 30 else "")
        session.metadata["title"] = title

    # Per-request database connection
    state._active_connector = None
    db_entry = None
    if req.db_id:
        db_entry = next((d for d in state._db_connections if d["id"] == req.db_id), None)
        session.metadata["db_id"] = req.db_id

    agent_messages = list(session.get_messages())

    if db_entry:
        try:
            db_path = db_entry.get("path", "")
            if db_path.startswith("~"):
                db_path = Path(db_path).expanduser().resolve()
            state._active_connector = DuckDBConnector(
                db_path=str(db_path),
                include_tables=db_entry.get("include_tables"),
                exclude_tables=db_entry.get("exclude_tables"),
            )
            state._active_connector.connect()
            tables = state._active_connector.get_schema()
            schema_text = build_schema_light(tables)
            logger.info(f"Connected to {db_entry['name']}: {len(tables)} tables")

            agent_messages.insert(0, {
                "role": "system",
                "content": f"你可以查询以下数据库。\n\n{schema_text}\n\n根据用户的问题，调用 query_database 工具来查询数据。"
            })
        except Exception as e:
            logger.error(f"Failed to load schema for {db_entry['name']}: {e}")
            agent_messages.insert(0, {
                "role": "system",
                "content": f"注意：你已连接到数据库「{db_entry['name']}」，但无法加载表结构（{e}）。请告知用户。"
            })

    session.add_message("user", req.message)
    agent_messages.append({"role": "user", "content": req.message})

    try:
        result = await state.agent_loop.run(agent_messages)
        content = result.get("content", "")
    except Exception as e:
        content = f"❌ 请求失败：{e}"
    finally:
        if state._active_connector:
            try:
                state._active_connector.disconnect()
            except Exception:
                pass
            state._active_connector = None

    session.add_message("assistant", content)

    return ChatResponse(
        reply=content,
        session_id=session_id,
        tool_calls=result.get("tool_calls", []) if 'result' in locals() else [],
    )
