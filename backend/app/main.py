"""Agentic Data Analyst — FastAPI server entry point."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .agent.loop import AgentLoop
from .agent.tools.registry import Tool, ToolRegistry
from .agent.tools.sql_tool import handle_sql_query
from .config import Config, load_config
from .db.base import DatabaseConnector
from .db.duckdb import DuckDBConnector
from .models.schemas import (
    ChatRequest,
    ChatResponse,
    ConfigUpdate,
    DBConnectRequest,
    DBInfo,
    DBTestResult,
    LLMTestResult,
    SessionRenameRequest,
    SessionMessagesResponse,
)
from .session.manager import SessionManager

# ---------------------------------------------------------------------------
# Global state (initialized at startup)
# ---------------------------------------------------------------------------

config: Config = None  # type: ignore
connector: DatabaseConnector = None  # type: ignore
tool_registry: ToolRegistry = None  # type: ignore
agent_loop: AgentLoop = None  # type: ignore
session_manager: SessionManager = None  # type: ignore
schema_prompt: str = ""
_config_store: dict = {}  # runtime config
_db_connections: list[dict] = []  # registered databases
_sqlite: sqlite3.Connection | None = None


def build_schema_prompt(tables) -> str:
    """Build the schema description injected into agent system prompt."""
    lines = ["以下是数据库中的表和字段：\n"]
    for t in tables:
        lines.append(t.to_prompt_block())
    return "\n".join(lines)


async def call_llm(messages: list[dict], **kwargs) -> object:
    """Unified LLM call — routes to the configured provider."""
    from openai import AsyncOpenAI

    client_kwargs = {}
    if config.llm.api_base:
        client_kwargs["base_url"] = config.llm.api_base

    api_key = config.llm.api_key or os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        client_kwargs["api_key"] = api_key

    client = AsyncOpenAI(**client_kwargs)
    response = await client.chat.completions.create(
        model=config.llm.model,
        messages=messages,
        **kwargs,
    )
    return response


async def handle_query_database(question: str) -> str:
    """Tool handler: query the database with a natural language question."""
    return await handle_sql_query(
        question=question,
        connector=connector,
        schema_prompt=schema_prompt,
        call_llm_func=lambda msgs: call_llm(msgs).choices[0].message.content,
        max_rows=config.safety.max_rows,
    )


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    global config, connector, tool_registry, agent_loop, session_manager, schema_prompt

    # 1. Load config
    config = load_config()

    # 2. Connect to database
    if config.database.type == "duckdb":
        connector = DuckDBConnector(
            db_path=config.database.path,
            include_tables=config.database.include_tables,
            exclude_tables=config.database.exclude_tables,
        )
    else:
        raise ValueError(f"Unsupported database type: {config.database.type}")

    connector.connect()
    tables = connector.get_schema()
    schema_prompt = build_schema_prompt(tables)
    print(f"📦 Connected to {config.database.type} — {len(tables)} tables found")

    # 3. Register tools
    tool_registry = ToolRegistry()

    # Register query_database tool
    tool_registry.register(Tool(
        name="query_database",
        description="用自然语言查询数据库。输入你想问的问题，我会生成 SQL 并返回查询结果。",
        parameters={
            "question": {
                "type": "string",
                "description": "关于数据的自然语言问题，如「上月销量最高的产品是什么」",
            }
        },
        handler=handle_query_database,
    ))

    # 4. Build system prompt for the agent
    system_prompt = f"""你是一个数据分析助手。用户会问你关于数据库中数据的问题。

你的工作流程：
1. 理解用户的问题
2. 如果需要查数据，调用 query_database 工具
3. 根据查询结果回答用户
4. 如果用户的问题不明确，主动澄清

可用的数据库表：
{schema_prompt}

注意事项：
- 如果用户问「帮我分析一下」，主动问他们想分析什么维度和时间段
- 使用中文回答
- 回答简洁，突出关键数据
- 如果工具返回了数据，直接根据数据回答，不要编造"""
    system_prompt += f"\n- 每次查询最多返回 {config.safety.max_rows} 行数据"

    if config.safety.read_only:
        system_prompt += "\n- 你只能查询数据，不能修改"

    # 5. Create agent loop
    agent_loop = AgentLoop(
        tool_registry=tool_registry,
        call_llm_func=lambda **kw: call_llm(**kw),
        system_prompt=system_prompt,
    )

    # 6. Init SQLite
    _init_sqlite()
    _load_config_sqlite()
    _load_db_connections_sqlite()

    # 7. Session manager
    session_manager = SessionManager(sqlite_conn=_sqlite)

    yield

    # Cleanup
    connector.disconnect()


# ---------------------------------------------------------------------------
# SQLite persistence (config + sessions + messages)
# ---------------------------------------------------------------------------


def _init_sqlite():
    """Initialize SQLite database with schema."""
    global _sqlite
    db_path = Path(config.storage.path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _sqlite = sqlite3.connect(str(db_path))
    _sqlite.execute("PRAGMA journal_mode=WAL")
    _sqlite.execute("PRAGMA busy_timeout=5000")

    _sqlite.executescript("""
        CREATE TABLE IF NOT EXISTS config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS databases (
            id                TEXT PRIMARY KEY,
            name              TEXT NOT NULL,
            type              TEXT NOT NULL DEFAULT 'duckdb',
            path              TEXT,
            connection_string TEXT,
            host              TEXT,
            port              INTEGER,
            username          TEXT,
            password          TEXT,
            db_name           TEXT,
            include_tables    TEXT,
            exclude_tables    TEXT,
            is_active         INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id         TEXT PRIMARY KEY,
            title      TEXT DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id),
            role      TEXT NOT NULL,
            content   TEXT NOT NULL DEFAULT '',
            tool_data TEXT,
            created_at REAL NOT NULL
        );
    """)


def _load_config_sqlite():
    """Load config from SQLite into runtime _config_store and config object."""
    global _config_store
    if _sqlite is None:
        return
    try:
        rows = _sqlite.execute("SELECT key, value FROM config").fetchall()
        _config_store = dict(rows)
        # Restore LLM config
        if "llm_provider" in _config_store:
            config.llm.provider = _config_store["llm_provider"]
        if "llm_model" in _config_store:
            config.llm.model = _config_store["llm_model"]
        if "llm_api_key" in _config_store:
            config.llm.api_key = _config_store["llm_api_key"]
        if "llm_api_base" in _config_store:
            config.llm.api_base = _config_store["llm_api_base"]
        if "safety_read_only" in _config_store:
            config.safety.read_only = _config_store["safety_read_only"] == "true"
        if "safety_max_rows" in _config_store:
            config.safety.max_rows = int(_config_store["safety_max_rows"])
    except Exception:
        pass


def _save_config_sqlite():
    """Save runtime config to SQLite."""
    if _sqlite is None:
        return
    pairs = [
        ("llm_provider", config.llm.provider),
        ("llm_model", config.llm.model),
        ("llm_api_key", config.llm.api_key),
        ("llm_api_base", config.llm.api_base or ""),
        ("safety_read_only", str(config.safety.read_only).lower()),
        ("safety_max_rows", str(config.safety.max_rows)),
    ]
    for key, value in pairs:
        _sqlite.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
    _sqlite.commit()


def _load_db_connections_sqlite():
    """Load database connections from SQLite."""
    global _db_connections
    if _sqlite is None:
        _db_connections = []
        return
    try:
        rows = _sqlite.execute("""
            SELECT id, name, type, path, connection_string, host, port,
                   username, db_name, include_tables, exclude_tables, is_active
            FROM databases ORDER BY name
        """).fetchall()
        _db_connections = []
        for r in rows:
            _db_connections.append({
                "id": r[0], "name": r[1], "type": r[2], "path": r[3],
                "connection_string": r[4], "host": r[5], "port": r[6],
                "user": r[7], "database": r[8],
                "include_tables": r[9].split(",") if r[9] else None,
                "exclude_tables": r[10].split(",") if r[10] else None,
                "is_active": bool(r[11]),
            })
    except Exception:
        _db_connections = []


def _save_db_connections_sqlite():
    """Save database connections to SQLite."""
    if _sqlite is None:
        return
    _sqlite.execute("DELETE FROM databases")
    for db in _db_connections:
        _sqlite.execute(
            "INSERT INTO databases (id, name, type, path, connection_string, host, port, "
            "username, password, db_name, include_tables, exclude_tables, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                db["id"], db["name"], db["type"], db.get("path"),
                db.get("connection_string"), db.get("host"), db.get("port"),
                db.get("user"), db.get("password"), db.get("database"),
                ",".join(db.get("include_tables") or []),
                ",".join(db.get("exclude_tables") or []),
                1 if db.get("is_active") else 0,
            ),
        )
    _sqlite.commit()


app = FastAPI(title="Agentic Data Analyst", lifespan=lifespan)

# Mount static assets (SPA build output)
ui_dir = Path(__file__).parent.parent.parent / "ui"
ui_dist = ui_dir / "dist" if ui_dir.exists() else None
if ui_dist and ui_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(ui_dist / "assets")), name="assets")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def root():
    index_path = (ui_dist / "index.html") if ui_dist else None
    if index_path and index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    # fallback: old static HTML
    legacy = ui_dir / "chat.html" if ui_dir else None
    if legacy and legacy.exists():
        return HTMLResponse(legacy.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Agentic Data Analyst</h1><p>UI not found.</p>")


@app.get("/api/schema")
async def get_schema():
    """Return database schema info for debugging."""
    if connector is None:
        raise HTTPException(503, "Database not connected")
    tables = connector.get_schema()
    return {
        "tables": [
            {
                "name": t.name,
                "columns": [
                    {"name": c.name, "type": c.data_type}
                    for c in (t.columns or [])
                ],
            }
            for t in tables
        ]
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if agent_loop is None:
        raise HTTPException(503, "Agent not initialized")

    # Check API key
    if not config.llm.api_key and not os.environ.get("OPENAI_API_KEY"):
        return ChatResponse(
            reply="⚠️ 请先在右侧配置面板中设置 LLM API Key，然后再提问。",
            session_id=req.session_id or "",
            tool_calls=[],
        )

    session_id = req.session_id or str(uuid.uuid4())[:8]
    session = session_manager.get_or_create(session_id)

    # Auto-title: use first user message as session title
    if not session.metadata.get("title") and len(session.messages) == 0:
        title = req.message[:30] + ("…" if len(req.message) > 30 else "")
        session.metadata["title"] = title

    # Add user message to session
    session.add_message("user", req.message)

    # Run agent loop
    try:
        result = await agent_loop.run(session.get_messages())
        content = result.get("content", "")
    except Exception as e:
        content = f"❌ 请求失败：{e}"

    # Add assistant response to session
    session.add_message("assistant", content)

    return ChatResponse(
        reply=content,
        session_id=session_id,
        tool_calls=result.get("tool_calls", []) if 'result' in locals() else [],
    )


@app.get("/api/sessions")
async def list_sessions():
    """List active sessions."""
    if session_manager is None:
        return {"sessions": []}
    return {
        "sessions": [
            {
                "id": s.session_id,
                "title": s.metadata.get("title", "新对话"),
                "messages": len(s.messages),
                "last_active": s.last_active,
            }
            for s in session_manager._sessions.values()
        ]
    }


@app.get("/api/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
async def get_session_messages(session_id: str):
    """Get messages for a specific session."""
    if session_manager is None:
        raise HTTPException(503, "Session manager not initialized")
    session = session_manager.get_or_create(session_id)
    return SessionMessagesResponse(
        session_id=session_id,
        messages=session.get_messages(),
    )


@app.patch("/api/sessions/{session_id}")
async def rename_session(session_id: str, req: SessionRenameRequest):
    """Rename a session."""
    if session_manager is None:
        raise HTTPException(503, "Session manager not initialized")
    session_manager.rename(session_id, req.title)
    return {"ok": True}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    if session_manager is None:
        raise HTTPException(503, "Session manager not initialized")
    session_manager.delete(session_id)
    return {"ok": True}


# ===== Database management =====


@app.get("/api/database")
async def list_databases():
    """List all registered databases."""
    return {"databases": _db_connections}


@app.get("/api/database/{db_id}/tables")
async def get_database_tables(db_id: str):
    """Connect to a registered database and return its table tree."""
    entry = next((d for d in _db_connections if d["id"] == db_id), None)
    if not entry:
        raise HTTPException(404, f"Database '{db_id}' not found")

    import os
    from pathlib import Path

    if entry["type"] == "duckdb":
        db_path = entry.get("path", "")
        if db_path.startswith("~"):
            db_path = Path(db_path).expanduser().resolve()
        if not os.path.exists(str(db_path)):
            raise HTTPException(404, f"DuckDB file not found: {db_path}")

        try:
            import duckdb
            import fnmatch
            conn = duckdb.connect(str(db_path))
            rows = conn.execute("""
                SELECT table_name, table_type FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
                ORDER BY table_type DESC, table_name
            """).fetchall()

            # Apply include/exclude filters
            include_patterns = entry.get("include_tables") or None
            exclude_patterns = entry.get("exclude_tables") or None

            filtered = []
            for table_name, table_type in rows:
                # Exclude takes priority
                if exclude_patterns:
                    skip = False
                    for p in exclude_patterns:
                        if p.endswith("*") and table_name.startswith(p[:-1]):
                            skip = True
                            break
                        if fnmatch.fnmatch(table_name, p):
                            skip = True
                            break
                    if skip:
                        continue

                # Include filter
                if include_patterns:
                    match = False
                    for p in include_patterns:
                        if p.endswith("*") and table_name.startswith(p[:-1]):
                            match = True
                            break
                        if fnmatch.fnmatch(table_name, p):
                            match = True
                            break
                    if not match:
                        continue

                filtered.append((table_name, table_type))
            tables = []
            for table_name, table_type in filtered:
                cols = conn.execute(f"""
                    SELECT column_name, data_type FROM information_schema.columns
                    WHERE table_name = '{table_name}'
                    ORDER BY ordinal_position
                """).fetchall()
                tables.append({
                    "name": table_name,
                    "type": table_type,
                    "columns": [{"name": c[0], "type": c[1]} for c in cols],
                })
            conn.close()
            return {"tables": tables}
        except Exception as e:
            raise HTTPException(500, f"Cannot read database: {e}")
    else:
        raise HTTPException(400, f"Table listing not supported for type: {entry['type']}")


@app.post("/api/database/connect")
async def connect_database(req: DBConnectRequest):
    """Register a new database connection."""
    db_id = str(uuid.uuid4())[:8]
    entry = {
        "id": db_id,
        "name": req.name or f"{req.type}-{db_id}",
        "type": req.type,
        "path": req.path,
        "connection_string": req.connection_string,
        "host": req.host,
        "port": req.port,
        "user": req.user,
        "database": req.database,
        "include_tables": req.include_tables,
        "exclude_tables": req.exclude_tables,
        "is_active": False,
    }
    _db_connections.append(entry)
    _save_db_connections_sqlite()
    return {"ok": True, "id": db_id, "message": f"已添加数据库 {entry['name']}"}


@app.post("/api/database/test")
async def test_database_connection(req: DBConnectRequest):
    """Test a database connection."""
    try:
        if req.type == "duckdb":
            test_conn = DuckDBConnector(
                db_path=req.path or ":memory:",
                include_tables=req.include_tables,
                exclude_tables=req.exclude_tables,
            )
            test_conn.connect()
            tables = test_conn.get_schema()
            test_conn.disconnect()
            return DBTestResult(ok=True, message=f"✅ 连接成功，发现 {len(tables)} 张表")
        else:
            return DBTestResult(ok=False, message=f"暂不支持 {req.type} 类型的测试")
    except Exception as e:
        return DBTestResult(ok=False, message=f"❌ 连接失败：{e}")


@app.delete("/api/database/{db_id}")
async def disconnect_database(db_id: str):
    """Remove a registered database."""
    global _db_connections
    _db_connections = [d for d in _db_connections if d["id"] != db_id]
    _save_db_connections_sqlite()
    return {"ok": True}


@app.patch("/api/database/{db_id}")
async def update_database(db_id: str, req: Request):
    """Update database connection settings (e.g. table filters)."""
    global _db_connections
    body = await req.json()
    entry = next((d for d in _db_connections if d["id"] == db_id), None)
    if not entry:
        raise HTTPException(404, f"Database '{db_id}' not found")

    if "include_tables" in body:
        entry["include_tables"] = body["include_tables"]
    if "exclude_tables" in body:
        entry["exclude_tables"] = body["exclude_tables"]

    _save_db_connections_sqlite()
    return {"ok": True, "message": f"已更新 {entry['name']} 的配置"}


# ===== Config management =====


@app.get("/api/config")
async def get_config():
    """Get current runtime configuration."""
    return {
        "llm": {
            "provider": config.llm.provider,
            "model": config.llm.model,
            "api_key": "••••••" if config.llm.api_key else "",
            "api_base": config.llm.api_base or "",
        },
        "safety": {
            "read_only": config.safety.read_only,
            "require_approval": True,
            "max_rows": config.safety.max_rows,
        },
    }


@app.post("/api/config")
async def update_config(req: ConfigUpdate):
    """Update runtime configuration."""
    if req.llm:
        if "provider" in req.llm:
            config.llm.provider = req.llm["provider"]
        if "model" in req.llm:
            config.llm.model = req.llm["model"]
        if "api_key" in req.llm and req.llm["api_key"] and req.llm["api_key"] != "••••••":
            config.llm.api_key = req.llm["api_key"]
        if "api_base" in req.llm:
            config.llm.api_base = req.llm["api_base"] or None
        _save_config_sqlite()
    if req.safety:
        if "read_only" in req.safety:
            config.safety.read_only = req.safety["read_only"]
        if "max_rows" in req.safety:
            config.safety.max_rows = req.safety["max_rows"]
        _save_config_sqlite()
    return {"ok": True}


@app.post("/api/config/llm/test", response_model=LLMTestResult)
async def test_llm(req: Request):
    """Test the LLM connection with provided (or saved) config."""
    body = await req.json() if req.headers.get("content-type") == "application/json" else {}

    test_key = body.get("api_key") or config.llm.api_key or os.environ.get("OPENAI_API_KEY", "")
    test_base = body.get("api_base") or config.llm.api_base or ""
    test_model = body.get("model") or config.llm.model or "gpt-4o"

    if not test_key:
        return LLMTestResult(ok=False, message="未设置 API Key")

    try:
        from openai import AsyncOpenAI

        client_kwargs = {"api_key": test_key}
        if test_base:
            client_kwargs["base_url"] = test_base

        client = AsyncOpenAI(**client_kwargs)
        await client.chat.completions.create(
            model=test_model,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=5,
        )
        return LLMTestResult(ok=True, message="连接成功")
    except Exception as e:
        err = str(e)
        return LLMTestResult(ok=False, message=err[:200])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    cfg = load_config()
    uvicorn.run(
        app,
        host=cfg.server.host,
        port=cfg.server.port,
        reload=True,
    )
