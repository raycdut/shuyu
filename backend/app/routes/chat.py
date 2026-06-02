"""Chat route — POST /api/chat"""

from __future__ import annotations

import asyncio
import datetime
import decimal
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .. import state
from ..agent.tools.registry import Tool
from ..agent.tools.sql_tool import handle_sql_query
from ..db.base import DatabaseConnector
from ..db.duckdb import DuckDBConnector
from ..db.mysql import MySQLConnector
from ..db.postgresql import PostgreSQLConnector
from ..db.schema import build_schema_light, build_schema_prompt
from ..client import call_llm
from ..models.chat import ChatRequest, ChatResponse

logger = logging.getLogger("shuyu.main")


def _create_connector(db_entry: dict) -> DatabaseConnector:
    """Create the appropriate database connector based on entry type."""
    db_type = db_entry.get("type", "duckdb")
    if db_type == "duckdb":
        db_path = db_entry.get("path", "")
        if db_path.startswith("~"):
            db_path = Path(db_path).expanduser().resolve()
        return DuckDBConnector(
            db_path=str(db_path),
            include_tables=db_entry.get("include_tables"),
            exclude_tables=db_entry.get("exclude_tables"),
        )
    elif db_type == "mysql":
        return MySQLConnector(
            host=db_entry.get("host", "127.0.0.1"),
            port=db_entry.get("port") or 3306,
            user=db_entry.get("user", "root"),
            password=db_entry.get("password", ""),
            database=db_entry.get("database", ""),
            include_tables=db_entry.get("include_tables"),
            exclude_tables=db_entry.get("exclude_tables"),
        )
    elif db_type == "postgres":
        return PostgreSQLConnector(
            host=db_entry.get("host", "127.0.0.1"),
            port=db_entry.get("port") or 5432,
            user=db_entry.get("user", "postgres"),
            password=db_entry.get("password", ""),
            database=db_entry.get("database", ""),
            include_tables=db_entry.get("include_tables"),
            exclude_tables=db_entry.get("exclude_tables"),
        )
    raise HTTPException(400, f"Unsupported database type: {db_type}")

router = APIRouter()


MAX_RESULT_ROWS = 100


# --- RAG integration helpers ---
_rag_config_cache = {"timestamp": 0.0, "enabled": False, "top_k": 5}


def _get_rag_enabled() -> bool:
    """Read RAG status from ConfigDB with 5s TTL cache (multi-worker safe)."""
    now = time.time()
    if now - _rag_config_cache["timestamp"] > 5:
        try:
            from ..admin_config.service import get_system_config
            config = get_system_config()
            rag = config.get("rag", {})
            _rag_config_cache["enabled"] = rag.get("enabled", False)
            _rag_config_cache["top_k"] = rag.get("top_k", 5)
            _rag_config_cache["timestamp"] = now
        except Exception:
            pass
    return _rag_config_cache["enabled"]


async def _get_schema_prompt(question: str, db_id: str, tables: list, connector) -> str:
    """Build schema prompt — uses RAG retrieval if enabled, full schema otherwise."""
    if not _get_rag_enabled():
        return build_schema_prompt(tables, db_id)
    try:
        from ..router.schema_retriever import retrieve_schema
        start = time.time()
        result = await retrieve_schema(
            question=question,
            database_id=db_id,
            tables=tables,
        )
        latency = int((time.time() - start) * 1000)
        from ..metrics.rag_metrics import record_query
        record_query(
            enabled=True,
            tier_hit=result.get("tier_hit", "unknown"),
            score=result.get("match_score", 0.0),
            latency_ms=latency,
            tables_retrieved=result.get("table_count", 0),
        )
        return result["prompt"]
    except Exception as e:
        logger.warning(f"RAG schema retrieval failed, using full schema: {e}")
        return build_schema_prompt(tables, db_id)


def _to_json_safe(obj):
    """递归将非 JSON 原生类型转换为可序列化的等效类型。

    DuckDB 的 datetime.date / datetime.datetime / decimal.Decimal 等类型
    无法被标准 json.dumps 序列化，需要预先转换。
    """
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json_safe(item) for item in obj]
    return obj


def _make_event(event: dict) -> str:
    """将 event dict 序列化为 SSE data 行，自动处理非 JSON 原生类型。"""
    return f"data: {json.dumps(_to_json_safe(event), ensure_ascii=False)}\n\n"


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Non-streaming chat endpoint for fast and quality modes."""
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

    if not req.db_id:
        session.add_message("user", f"<user_query>\n{req.message}\n</user_query>")
        content = "⚠️ 请先在左侧选择一个数据库，然后再提问。"
        session.add_message("assistant", content)
        return ChatResponse(
            reply=content,
            session_id=session_id,
            tool_calls=[],
            sql_queries=[],
            query_results=[],
        )

    # Auto-title
    if not session.metadata.get("title") and len(session.messages) == 0:
        title = req.message[:30] + ("…" if len(req.message) > 30 else "")
        session.metadata["title"] = title

    # Per-request state
    sql_queries_collector: list[str] = []
    query_results_collector: list[dict] = []
    tok_sql = state.request_sql_queries.set(sql_queries_collector)
    tok_qr = state.request_query_results.set(query_results_collector)
    tok_conn = state.request_active_connector.set(None)
    tok_schema = state.request_schema_prompt.set(None)
    tok_db = state.request_active_db_id.set(req.db_id or None)
    active_connector = None
    db_entry = None
    if req.db_id:
        prev_db = session.metadata.get("db_id")
        db_entry = next((d for d in state._db_connections if d["id"] == req.db_id), None)
        session.metadata["db_id"] = req.db_id

    agent_messages = list(session.get_messages())

    if db_entry:
        schema_text = "当前无法加载表结构"
        full_schema_text = None
        same_db = req.db_id and req.db_id == session.metadata.get("_cached_db_id")
        if same_db and "_schema" in session.metadata:
            # Reuse cached schema, but always create a fresh connector per request
            schema_text = session.metadata["_schema"]
            full_schema_text = session.metadata.get("_schema_full")
            try:
                active_connector = _create_connector(db_entry)
                active_connector.connect()
                state.request_active_connector.set(active_connector)
                state.request_active_db_id.set(req.db_id)
                if full_schema_text:
                    state.request_schema_prompt.set(full_schema_text)
                logger.info(f"Session {session_id}: reuse cached schema ({db_entry['name']})")
            except Exception as e:
                logger.error(f"Failed to connect to {db_entry['name']}: {e}")
                agent_messages.insert(0, {
                    "role": "system",
                    "content": f"注意：你已选择数据库「{db_entry['name']}」，但无法连接（{e}）。请告知用户。"
                })
        else:
            # First time or DB changed — connect fresh
            try:
                active_connector = _create_connector(db_entry)
                active_connector.connect()
                state.request_active_connector.set(active_connector)
                state.request_active_db_id.set(req.db_id)
                tables = active_connector.get_schema()
                schema_text = build_schema_light(tables, req.db_id)
                full_schema_text = build_schema_prompt(tables, req.db_id)
                state.request_schema_prompt.set(full_schema_text)
                logger.info(f"Connected to {db_entry['name']}: {len(tables)} tables")

                # Cache in session
                session.metadata["_schema"] = schema_text
                session.metadata["_schema_full"] = full_schema_text
                session.metadata["_cached_db_id"] = req.db_id
            except Exception as e:
                logger.error(f"Failed to load schema for {db_entry['name']}: {e}")
                agent_messages.insert(0, {
                    "role": "system",
                    "content": f"注意：你已连接到数据库「{db_entry['name']}」，但无法加载表结构（{e}）。请告知用户。"
                })

        # Inject schema — use RAG if enabled, full schema otherwise
        if _get_rag_enabled():
            inject_schema = await _get_schema_prompt(req.message, req.db_id, tables, active_connector)
        else:
            inject_schema = schema_text
            if req.mode == "quality" and db_entry:
                if full_schema_text:
                    inject_schema = full_schema_text
        agent_messages.insert(0, {
            "role": "system",
            "content": f"<database name=\"{db_entry['name']}\">\n{inject_schema}\n</database>\n<instruction>以上 <database> 标签中已完整列出所有可用表、字段和业务描述。关于表结构、有哪些表等元数据问题，请直接使用以上信息回答，不要查询数据库。</instruction>\n<instruction>对于具体的数据查询（如销量、订单量、用户数等），调用 query_database 工具。</instruction>"
        })

    safe_message = f"<user_query>\n{req.message}\n</user_query>"
    session.add_message("user", safe_message)
    agent_messages.append({"role": "user", "content": safe_message})

    # Run agent (fast or quality mode)
    agent = state.advanced_agent if req.mode == "quality" else state.agent_loop
    logger.info(f"Using agent: {'quality' if req.mode == 'quality' else 'fast'} mode")

    try:
        result = await agent.run(agent_messages)
        content = result.get("content", "")

        # Collect SQL queries — AdvancedAgent returns them in result, SimpleAgent uses global state
        sql_queries = result.get("sql_queries") or state.get_request_sql_queries()

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
        state.request_schema_prompt.reset(tok_schema)
        state.request_active_connector.reset(tok_conn)
        state.request_active_db_id.reset(tok_db)
        state.request_sql_queries.reset(tok_sql)
        state.request_query_results.reset(tok_qr)
        if active_connector:
            try:
                active_connector.disconnect()
            except Exception:
                pass
            active_connector = None

    session.add_message("assistant", content)

    # Fire-and-forget self-learning (Phase 5)
    if sql_queries_collector:
        try:
            from ..router.question_learner import learn as rag_learn
            import asyncio
            asyncio.ensure_future(rag_learn(
                question=req.message,
                sql=sql_queries_collector[0] if sql_queries_collector else "",
                tables=[],  # table names extracted from SQL if needed
                database_id=req.db_id or "",
                success=bool(query_results_collector),
                self_learn_enabled=_get_rag_enabled(),
            ))
        except Exception:
            pass

    # Store query_results in session metadata for persistence
    try:
        session.metadata["_query_results"] = _to_json_safe(
            query_results_collector
        )
    except Exception:
        pass

    return ChatResponse(
        reply=content,
        session_id=session_id,
        tool_calls=result.get("tool_calls", []) if 'result' in locals() else [],
        sql_queries=(result.get("sql_queries") or sql_queries_collector) if 'result' in locals() else sql_queries_collector,
        query_results=query_results_collector,
    )


@router.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """Streaming chat — returns SSE events for agent progress."""
    from fastapi.responses import StreamingResponse

    async def event_stream():
        """Server-sent events generator for quality-mode progress."""
        try:
            if state.agent_loop is None:
                yield _make_event({'type': 'error', 'content': 'Agent not initialized'})
                return

            yield _make_event({'type': 'thinking', 'content': '正在分析问题...'})

            # Session + DB setup (same as POST /api/chat)
            session_id = req.session_id or str(uuid.uuid4())[:8]
            session = state.session_manager.get_or_create(session_id)

            if not req.db_id:
                session.add_message("user", req.message)
                content = "⚠️ 请先在左侧选择一个数据库，然后再提问。"
                yield _make_event({'type': 'session_id', 'session_id': session_id})
                yield _make_event({'type': 'done', 'content': content, 'sql_queries': [], 'query_results': []})
                session.add_message("assistant", content)
                return

            if not session.metadata.get("title") and len(session.messages) == 0:
                title = req.message[:30] + ("…" if len(req.message) > 30 else "")
                session.metadata["title"] = title

            sql_queries_collector: list[str] = []
            query_results_collector: list[dict] = []
            tok_sql = state.request_sql_queries.set(sql_queries_collector)
            tok_qr = state.request_query_results.set(query_results_collector)
            tok_conn = state.request_active_connector.set(None)
            tok_schema = state.request_schema_prompt.set(None)
            tok_db = state.request_active_db_id.set(req.db_id or None)
            active_connector = None
            db_entry = None
            if req.db_id:
                db_entry = next((d for d in state._db_connections if d["id"] == req.db_id), None)
                session.metadata["db_id"] = req.db_id

            agent_messages = list(session.get_messages())
            if db_entry:
                schema_text = "当前无法加载表结构"
                full_schema_text = None
                same_db = req.db_id and req.db_id == session.metadata.get("_cached_db_id")
                try:
                    if same_db and "_schema" in session.metadata:
                        schema_text = session.metadata["_schema"]
                        full_schema_text = session.metadata.get("_schema_full")
                        active_connector = _create_connector(db_entry)
                        active_connector.connect()
                        state.request_active_connector.set(active_connector)
                        state.request_active_db_id.set(req.db_id)
                        if full_schema_text:
                            state.request_schema_prompt.set(full_schema_text)
                    else:
                        active_connector = _create_connector(db_entry)
                        active_connector.connect()
                        state.request_active_connector.set(active_connector)
                        state.request_active_db_id.set(req.db_id)
                        tables = active_connector.get_schema()
                        schema_text = build_schema_light(tables, req.db_id)
                        full_schema_text = build_schema_prompt(tables, req.db_id)
                        state.request_schema_prompt.set(full_schema_text)
                        session.metadata["_schema"] = schema_text
                        session.metadata["_schema_full"] = full_schema_text
                        session.metadata["_cached_db_id"] = req.db_id

                    if _get_rag_enabled():
                        s_text = await _get_schema_prompt(req.message, req.db_id, tables, active_connector)
                    else:
                        s_text = (
                            full_schema_text
                            if (req.mode == "quality" and full_schema_text)
                            else schema_text
                        )
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
                        yield _make_event(event)
                        if event.get("type") == "done":
                            done_event = event
                            break
                        elif event.get("type") == "error":
                            break
                except asyncio.CancelledError:
                    agent_task.cancel()
                    raise
                finally:
                    if done_event is None:
                        agent_task.cancel()
                    try:
                        await agent_task
                    except (asyncio.CancelledError, Exception):
                        pass

                content = done_event["content"] if done_event else ""
                sql_queries = done_event.get("sql_queries") if done_event else []
                query_results = done_event.get("query_results") if done_event else []
                # Send session_id so frontend can continue the conversation
                yield _make_event({'type': 'session_id', 'session_id': session_id})
            else:
                # Fast mode: wait then return
                result = await agent_task
                content = result.get("content", "")
                sql_queries = result.get("sql_queries") or state.get_request_sql_queries()
                query_results = result.get("query_results") or state.get_request_query_results()

            state.request_schema_prompt.reset(tok_schema)
            state.request_active_connector.reset(tok_conn)
            state.request_active_db_id.reset(tok_db)
            state.request_sql_queries.reset(tok_sql)
            state.request_query_results.reset(tok_qr)
            if active_connector:
                try:
                    active_connector.disconnect()
                except Exception:
                    pass
                active_connector = None

            session.add_message("assistant", content)

            # Store query_results in session metadata for persistence
            if query_results:
                try:
                    session.metadata["_query_results"] = _to_json_safe(query_results)
                except Exception:
                    pass

            # Final done event for fast mode
            if req.mode != "quality":
                yield _make_event({'type': 'done', 'content': content, 'sql_queries': sql_queries, 'query_results': query_results})

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield _make_event({'type': 'error', 'content': str(e)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
