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
from .routes import admin_stats, chat, config as config_route, database, schema, sessions
from .auth.router import router as auth_router
from .auth.service import init_auth_config
from .admin_config.router import router as admin_config_router
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
    """Configure file + stderr logging (after uvicorn starts).

    Log file rotates based on storage.log_interval config:
    - "hour" → one file per hour (shuyu.YYYY-MM-DD_HH.log)
    - "day"  → one file per day  (shuyu.YYYY-MM-DD.log)
    """
    import logging as _logging
    from logging.handlers import TimedRotatingFileHandler

    from .config import PROJECT_ROOT

    root = _logging.getLogger()
    # Remove uvicorn handlers
    for h in list(root.handlers):
        root.removeHandler(h)
    # Add our handlers
    root.setLevel(_logging.INFO)
    fmt = _logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s")

    log_dir = PROJECT_ROOT / "backend" / "data"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = str(log_dir / "shuyu.log")

    interval = state.config.storage.log_interval
    when = "H" if interval == "hour" else "MIDNIGHT"
    suffix = "%Y-%m-%d_%H" if interval == "hour" else "%Y-%m-%d"
    retention = state.config.storage.log_retention_days

    fh = TimedRotatingFileHandler(
        log_path,
        when=when,
        interval=1,
        backupCount=retention,
    )
    fh.suffix = suffix
    fh.setFormatter(fmt)
    root.addHandler(fh)
    sh = _logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global config, connector, tool_registry, agent_loop, session_manager, schema_prompt

    # 0. Load config first (logging setup needs it)
    state.config = load_config()
    _setup_logging()
    logger.info(f"Config loaded: LLM={state.config.llm.provider}/{state.config.llm.model}")

    # 1.1 Init auth config (JWT secret etc.)
    init_auth_config()

    # 2. Init SQLite persistence
    init_sqlite()
    load_config_sqlite()
    load_db_connections_sqlite()
    logger.info(f"SQLite ready: {len(state._db_connections)} DB connections loaded")

    # 3. Register tools
    state.tool_registry = ToolRegistry()
    state.tool_registry.register(Tool(
        name="query_database",
        description="查询数据库。传入自然语言问题（question）会自动生成 SQL，或直接传入 SQL（sql）执行。",
        parameters={
            "question": {
                "type": "string",
                "description": "关于数据的自然语言问题，如「上月销量最高的产品是什么」（与 sql 二选一）",
            },
            "sql": {
                "type": "string",
                "description": "直接传入 SQL 查询语句执行（与 question 二选一）",
            },
        },
        required=[],
        handler=handle_query_database,
    ))

    # 4. Load all prompt categories (from DB with hardcoded fallbacks)
    from .persistence import _get_default_prompt_content

    PROMPT_CATEGORIES = ["system", "sql_gen", "plan", "plan_reflect", "report_reflect", "schema_describe"]
    loaded_prompts: dict[str, str] = {}
    for cat in PROMPT_CATEGORIES:
        content = None
        if state._sqlite:
            row = state._sqlite.execute(
                "SELECT content FROM prompts WHERE name = ? AND is_active = 1 ORDER BY created_at DESC LIMIT 1",
                (cat,),
            ).fetchone()
            if row:
                content = row[0]
        if not content:
            content = _get_default_prompt_content(cat) or ""
        loaded_prompts[cat] = content

    # Store prompts in state for other modules (sql_tool, describe_schema_agent, etc.)
    state.sql_gen_prompt = loaded_prompts["sql_gen"]
    state.plan_prompt = loaded_prompts["plan"]
    state.plan_reflect_prompt = loaded_prompts["plan_reflect"]
    state.report_reflect_prompt = loaded_prompts["report_reflect"]
    state.schema_describe_prompt = loaded_prompts["schema_describe"]

    # Build system prompt with read-only override
    system_prompt = loaded_prompts["system"]
    if state.config.safety.read_only:
        system_prompt = system_prompt.replace("</rules>", "    <rule>你只能查询数据，不能修改</rule>\n  </rules>")

    logger.info("All prompt categories loaded from DB" if state._sqlite else "All prompt categories loaded (fallback)")
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
        plan_prompt=loaded_prompts["plan"],
        plan_reflect_prompt=loaded_prompts["plan_reflect"],
        report_reflect_prompt=loaded_prompts["report_reflect"],
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
app.include_router(auth_router)
app.include_router(admin_config_router)
app.include_router(schema.router)
app.include_router(chat.router)
app.include_router(sessions.router)
app.include_router(database.router)
app.include_router(config_route.router)
app.include_router(admin_stats.router)


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
