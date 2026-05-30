"""Agentic Data Analyst — FastAPI server entry point (slim).

App assembly: lifespan → load config/persistence → register tools → mount routes.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import state
from .agent.advanced_agent import AdvancedAgent
from .agent.simple_agent import SimpleAgent
from .agent.tools.registry import Tool, ToolRegistry
from .config import load_config
from .persistence import init_sqlite
from .persistence.config import load_config_sqlite
from .persistence.database import load_db_connections_sqlite
from .client import call_llm
from .agent.tools.sql_tool import handle_query_database
from .routes import chat, config as config_route, database, schema, sessions
from .session.manager import SessionManager

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("shuyu.main")
for name in ("shuyu.main", "shuyu.session", "shuyu.agent", "shuyu.registry", "shuyu.db"):
    l = logging.getLogger(name)
    l.setLevel(logging.INFO)
    l.propagate = True

# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


def _setup_logging():
    """Configure file + stderr logging (after uvicorn starts)."""
    import logging as _logging
    root = _logging.getLogger()
    # Remove uvicorn handlers
    for h in list(root.handlers):
        root.removeHandler(h)
    # Add our handlers
    root.setLevel(_logging.INFO)
    fmt = _logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s")
    fh = _logging.FileHandler("./data/shuyu.log")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    sh = _logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global config, connector, tool_registry, agent_loop, session_manager, schema_prompt

    # 0. Setup logging
    _setup_logging()
    state.config = load_config()
    logger.info(f"Config loaded: LLM={state.config.llm.provider}/{state.config.llm.model}")

    # 2. Init SQLite persistence
    init_sqlite()
    load_config_sqlite()
    load_db_connections_sqlite()
    logger.info(f"SQLite ready: {len(state._db_connections)} DB connections loaded")

    # 3. Register tools
    state.tool_registry = ToolRegistry()
    state.tool_registry.register(Tool(
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

    # 4. Build system prompt (from DB with fallback)
    system_prompt = None
    if state._sqlite:
        row = state._sqlite.execute(
            "SELECT content FROM prompts WHERE is_active = 1 ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if row:
            system_prompt = row[0]
    if not system_prompt:
        system_prompt = (
            "<instructions>\n"
            "  <role>data-analyst</role>\n"
            "  <language>zh-CN</language>\n"
            "  <workflow>\n"
            "    <step>1. 理解用户的问题</step>\n"
            "    <step>2. 必须调用 query_database 工具查询数据，不能凭表名猜测</step>\n"
            "    <step>3. 根据查询结果回答用户</step>\n"
            "    <step>4. 如果用户的问题不明确，主动澄清</step>\n"
            "  </workflow>\n"
            "  <rules>\n"
            "    <rule>如果用户问「帮我分析一下」，主动问他们想分析什么维度和时间段</rule>\n"
            "    <rule>使用中文回答</rule>\n"
            "    <rule>回答简洁，突出关键数据</rule>\n"
            "    <rule>如果工具返回了数据，直接根据数据回答，不要编造</rule>\n"
            f"    <rule>每次查询最多返回 {state.config.safety.max_rows} 行数据</rule>\n"
            "  </rules>\n"
            "</instructions>"
        )
    if state.config.safety.read_only:
        system_prompt = system_prompt.replace("</rules>", "    <rule>你只能查询数据，不能修改</rule>\n  </rules>")
    logger.info("System prompt loaded from DB" if state._sqlite and row else "System prompt loaded (fallback)")
    logger.info("Creating ReAct agent loop...")
    state.agent_loop = SimpleAgent(
        tool_registry=state.tool_registry,
        call_llm_func=call_llm,
        system_prompt=system_prompt,
    )
    state.advanced_agent = AdvancedAgent(
        tool_registry=state.tool_registry,
        call_llm_func=call_llm,
        system_prompt=system_prompt,
    )

    # 6. Session manager
    state.session_manager = SessionManager(sqlite_conn=state._sqlite)
    logger.info(f"Shuyu ready — {len(state.session_manager._sessions)} sessions loaded")

    yield

    # Cleanup
    if state.connector:
        state.connector.disconnect()


# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------

app = FastAPI(title="Shuyu — Data Chat", lifespan=lifespan)

# CORS: allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static assets (SPA build output)
ui_dir = Path(__file__).parent.parent.parent / "ui"
ui_dist = ui_dir / "dist" if ui_dir.exists() else None
if ui_dist and ui_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(ui_dist / "assets")), name="assets")

# Register routers
app.include_router(schema.router)
app.include_router(chat.router)
app.include_router(sessions.router)
app.include_router(database.router)
app.include_router(config_route.router)


# ---------------------------------------------------------------------------
# Root route
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def root():
    index_path = (ui_dist / "index.html") if ui_dist else None
    if index_path and index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    legacy = ui_dir / "chat.html" if ui_dir else None
    if legacy and legacy.exists():
        return HTMLResponse(legacy.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Agentic Data Analyst</h1><p>UI not found.</p>")


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
