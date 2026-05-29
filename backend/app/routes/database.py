"""Database management routes"""

from __future__ import annotations

import fnmatch
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from .. import state
from ..config_store import save_db_connections_sqlite
from ..db.duckdb import DuckDBConnector
from ..models.database import DBConnectRequest, DBTestResult

logger = logging.getLogger("shuyu.main")

router = APIRouter()


@router.get("/api/database")
async def list_databases():
    """List all registered databases."""
    logger.info(f"GET /api/database: {len(state._db_connections)} connections")
    return {"databases": state._db_connections}


@router.get("/api/database/{db_id}/tables")
async def get_database_tables(db_id: str):
    """Connect to a registered database and return its table tree."""
    entry = next((d for d in state._db_connections if d["id"] == db_id), None)
    logger.info(f"GET /api/database/{db_id}/tables")
    if not entry:
        raise HTTPException(404, f"Database '{db_id}' not found")

    if entry["type"] == "duckdb":
        db_path = entry.get("path", "")
        if db_path.startswith("~"):
            db_path = Path(db_path).expanduser().resolve()
        if not os.path.exists(str(db_path)):
            raise HTTPException(404, f"DuckDB file not found: {db_path}")

        try:
            import duckdb
            conn = duckdb.connect(str(db_path))
            rows = conn.execute("""
                SELECT table_name, table_type FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
                ORDER BY table_type DESC, table_name
            """).fetchall()

            include_patterns = entry.get("include_tables") or None
            exclude_patterns = entry.get("exclude_tables") or None

            filtered = []
            for table_name, table_type in rows:
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

    raise HTTPException(400, f"Table listing not supported for type: {entry['type']}")


@router.post("/api/database/connect")
async def connect_database(req: DBConnectRequest):
    """Register a new database connection."""
    logger.info(f"POST /api/database/connect: name={req.name} type={req.type}")

    if any(d["name"].lower() == req.name.lower() for d in state._db_connections):
        logger.warning(f"Duplicate database name: {req.name}")
        raise HTTPException(409, f"数据库名称「{req.name}」已存在")

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
    state._db_connections.append(entry)
    save_db_connections_sqlite()
    return {"ok": True, "id": db_id, "message": f"已添加数据库 {entry['name']}"}


@router.post("/api/database/test")
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


@router.delete("/api/database/{db_id}")
async def disconnect_database(db_id: str):
    """Remove a registered database."""
    logger.info(f"DELETE /api/database/{db_id}")
    state._db_connections = [d for d in state._db_connections if d["id"] != db_id]
    save_db_connections_sqlite()
    return {"ok": True}


@router.patch("/api/database/{db_id}")
async def update_database(db_id: str, req: Request):
    """Update database connection settings (e.g. table filters)."""
    body = await req.json()
    logger.info(f"PATCH /api/database/{db_id}: include={body.get('include_tables')} exclude={body.get('exclude_tables')}")

    entry = next((d for d in state._db_connections if d["id"] == db_id), None)
    if not entry:
        raise HTTPException(404, f"Database '{db_id}' not found")

    if "include_tables" in body:
        entry["include_tables"] = body["include_tables"]
    if "exclude_tables" in body:
        entry["exclude_tables"] = body["exclude_tables"]

    save_db_connections_sqlite()
    return {"ok": True, "message": f"已更新 {entry['name']} 的配置"}
