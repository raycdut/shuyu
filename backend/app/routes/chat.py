"""Chat route — POST /api/chat"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .. import state
from ..agent.tools.registry import Tool
from ..agent.tools.sql_tool import handle_sql_query
from ..db.duckdb import DuckDBConnector
from ..db.schema import build_schema_light, build_schema_prompt
from ..client import call_llm
from ..models.chat import ChatRequest, ChatResponse

logger = logging.getLogger("shuyu.main")

router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if state.agent_loop is None:
        raise HTTPException(503, "Agent not initialized")

    logger.info(f"POST /api/chat  session={req.session_id or 'new'}  db={req.db_id or 'none'}  mode={req.mode}  msg={req.message[:50]}...")

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

    # Per-request state
    state._active_connector = None
    state._last_sql_queries = []
    db_entry = None
    if req.db_id:
        prev_db = session.metadata.get("db_id")
        db_entry = next((d for d in state._db_connections if d["id"] == req.db_id), None)
        session.metadata["db_id"] = req.db_id

    agent_messages = list(session.get_messages())

    if db_entry:
        same_db = req.db_id and req.db_id == session.metadata.get("_cached_db_id")
        if same_db and "_schema" in session.metadata:
            # Reuse cached connector and schema
            state._active_connector = session.metadata.get("_connector")
            schema_text = session.metadata["_schema"]
            logger.info(f"Session {session_id}: reuse cached connection ({db_entry['name']})")
        else:
            # First time or DB changed — connect fresh
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

                # Cache in session
                session.metadata["_connector"] = state._active_connector
                session.metadata["_schema"] = schema_text
                session.metadata["_cached_db_id"] = req.db_id
            except Exception as e:
                logger.error(f"Failed to load schema for {db_entry['name']}: {e}")
                agent_messages.insert(0, {
                    "role": "system",
                    "content": f"注意：你已连接到数据库「{db_entry['name']}」，但无法加载表结构（{e}）。请告知用户。"
                })

        # Inject schema — use full schema for quality mode, light for fast mode
        inject_schema = schema_text
        if req.mode == "quality" and db_entry:
            try:
                tables = state._active_connector.get_schema() if state._active_connector else []
                if tables:
                    inject_schema = build_schema_prompt(tables)
            except Exception:
                pass
        agent_messages.insert(0, {
            "role": "system",
            "content": f"<database name=\"{db_entry['name']}\">\n{inject_schema}\n</database>\n<instruction>你必须调用 query_database 工具来查询数据，不要凭表名猜测答案。</instruction>"
        })

    session.add_message("user", req.message)
    agent_messages.append({"role": "user", "content": req.message})

    # Run agent (fast or quality mode)
    agent = state.advanced_agent if req.mode == "quality" else state.agent_loop
    logger.info(f"Using agent: {'quality' if req.mode == 'quality' else 'fast'} mode")

    try:
        result = await agent.run(agent_messages)
        content = result.get("content", "")

        # Collect SQL queries — AdvancedAgent returns them in result, SimpleAgent uses global state
        sql_queries = result.get("sql_queries") or state._last_sql_queries or []

        # Post-process: ensure [QN] markers appear when SQL was executed
        if sql_queries and not re.search(r"\[Q\d+\]", content):
            q_count = len(sql_queries)
            if q_count > 1:
                content += f"\n---\n💡 以上数据来自 {q_count} 次查询"
            elif q_count == 1:
                content = content.replace("数据", f"[Q1]数据", 1) if "数据" in content else content
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
        sql_queries=result.get("sql_queries") or state._last_sql_queries or [],
    )


@router.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """Streaming chat — returns SSE events for agent progress."""
    from fastapi.responses import StreamingResponse

    async def event_stream():
        try:
            if state.agent_loop is None:
                yield f"data: {json.dumps({'type': 'error', 'content': 'Agent not initialized'})}\n\n"
                return

            yield f"data: {json.dumps({'type': 'thinking', 'content': '正在分析问题...'})}\n\n"

            # Session + DB setup (same as POST /api/chat)
            session_id = req.session_id or str(uuid.uuid4())[:8]
            session = state.session_manager.get_or_create(session_id)

            if not session.metadata.get("title") and len(session.messages) == 0:
                title = req.message[:30] + ("…" if len(req.message) > 30 else "")
                session.metadata["title"] = title

            state._active_connector = None
            state._last_sql_queries = []
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
                    # Use full schema for quality mode
                    s_text = build_schema_prompt(tables) if req.mode == "quality" else build_schema_light(tables)
                    agent_messages.insert(0, {
                        "role": "system",
                        "content": f"<database name=\"{db_entry['name']}\">\n{s_text}\n</database>\n<instruction>你必须调用 query_database 工具来查询数据，不要凭表名猜测答案。</instruction>"
                    })
                except Exception as e:
                    agent_messages.insert(0, {
                        "role": "system",
                        "content": f"注意：你已连接到数据库「{db_entry['name']}」，但无法加载表结构（{e}）。"
                    })

            session.add_message("user", req.message)
            agent_messages.append({"role": "user", "content": req.message})

            # Run agent
            agent = state.advanced_agent if req.mode == "quality" else state.agent_loop
            progress_queue: asyncio.Queue = asyncio.Queue()

            async def on_progress(event: dict):
                await progress_queue.put(event)

            # Run agent in background, collect result
            agent_task = asyncio.create_task(
                agent.run(agent_messages, progress_callback=on_progress if req.mode == "quality" else None)
            )

            if req.mode == "quality":
                # Stream progress events
                done_event = None
                try:
                    while True:
                        event = await progress_queue.get()
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                        if event.get("type") == "done":
                            done_event = event
                            break
                        elif event.get("type") == "error":
                            break
                finally:
                    # Ensure agent_task is properly cleaned up
                    agent_task.cancel()
                    try:
                        await agent_task
                    except (asyncio.CancelledError, Exception):
                        pass

                content = done_event["content"] if done_event else ""
                # Send session_id so frontend can continue the conversation
                yield f"data: {json.dumps({'type': 'session_id', 'session_id': session_id})}\n\n"
            else:
                # Fast mode: wait then return
                result = await agent_task
                content = result.get("content", "")

            if state._active_connector:
                try:
                    state._active_connector.disconnect()
                except Exception:
                    pass
                state._active_connector = None

            session.add_message("assistant", content)

            # Final done event for fast mode
            if req.mode != "quality":
                yield f"data: {json.dumps({'type': 'done', 'content': content})}\n\n"

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
