"""Database management routes"""

from __future__ import annotations

import fnmatch
import json
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import state
from ..auth.middleware import get_current_user, require_admin
from ..persistence.database import save_db_connections_sqlite
from ..persistence.schema import (
    get_schema_status,
    load_full_schema,
    save_descriptions,
    save_imported_schema,
    update_database_schema_status,
    update_description,
)
from ..db.duckdb import DuckDBConnector
from ..models.database import (
    DBConnectRequest,
    DBTestResult,
    DescriptionGenerateRequest,
    DescriptionUpdateRequest,
    SchemaImportRequest,
    SchemaStatusResponse,
)

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
                cols = conn.execute("""
                    SELECT column_name, data_type FROM information_schema.columns
                    WHERE table_name = ?
                    ORDER BY ordinal_position
                """, (table_name,)).fetchall()
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
async def connect_database(req: DBConnectRequest, _admin: dict = Depends(require_admin)):
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

    from ..admin_config.service import log_database_change
    log_database_change(
        _admin["username"],
        f"添加数据库连接: {entry['name']} (类型: {req.type})",
    )

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
async def disconnect_database(db_id: str, _admin: dict = Depends(require_admin)):
    """Remove a registered database."""
    logger.info(f"DELETE /api/database/{db_id}")
    entry = next((d for d in state._db_connections if d["id"] == db_id), None)
    db_name = entry["name"] if entry else db_id
    state._db_connections = [d for d in state._db_connections if d["id"] != db_id]
    save_db_connections_sqlite()

    from ..admin_config.service import log_database_change
    log_database_change(
        _admin["username"],
        f"删除数据库连接: {db_name}",
    )

    return {"ok": True}


@router.patch("/api/database/{db_id}")
async def update_database(db_id: str, req: Request, _admin: dict = Depends(require_admin)):
    """Update database connection settings."""
    body = await req.json()
    logger.info(f"PATCH /api/database/{db_id}")

    entry = next((d for d in state._db_connections if d["id"] == db_id), None)
    if not entry:
        raise HTTPException(404, f"Database '{db_id}' not found")

    # Update allowed fields
    changed_fields = []
    for field in ("name", "path", "connection_string", "host", "port", "user", "password", "database",
                  "include_tables", "exclude_tables"):
        if field in body:
            old_val = entry.get(field)
            new_val = body[field]
            if old_val != new_val:
                changed_fields.append(field)
            entry[field] = body[field]

    save_db_connections_sqlite()

    if changed_fields:
        from ..admin_config.service import log_database_change
        log_database_change(
            _admin["username"],
            f"更新数据库连接: {entry['name']} — 修改字段: {', '.join(changed_fields)}",
        )

    return {"ok": True, "message": f"已更新 {entry['name']} 的配置"}


@router.post("/api/database/{db_id}/schema/import")
async def import_schema(db_id: str, req: SchemaImportRequest, _admin: dict = Depends(require_admin)):
    """Connect to a database and import its schema (tables & columns) into local storage."""
    logger.info(f"POST /api/database/{db_id}/schema/import")

    entry = next((d for d in state._db_connections if d["id"] == db_id), None)
    if not entry:
        raise HTTPException(404, f"Database '{db_id}' not found")

    update_database_schema_status(db_id, "importing")
    try:
        include = req.include_tables or entry.get("include_tables")
        exclude = req.exclude_tables or entry.get("exclude_tables")

        if entry["type"] == "duckdb":
            db_path = entry.get("path", "")
            if db_path.startswith("~"):
                db_path = Path(db_path).expanduser().resolve()
            if not os.path.exists(str(db_path)):
                update_database_schema_status(db_id, "error")
                raise HTTPException(404, f"DuckDB file not found: {db_path}")

            import duckdb
            conn = duckdb.connect(str(db_path))
            rows = conn.execute("""
                SELECT table_name, table_type FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
                ORDER BY table_name
            """).fetchall()

            tables_data = []
            for table_name, table_type in rows:
                if _should_exclude(table_name, include, exclude):
                    continue
                cols = conn.execute("""
                    SELECT column_name, data_type, is_nullable,
                           COALESCE(column_default, '') as column_default
                    FROM information_schema.columns
                    WHERE table_name = ?
                      AND table_schema NOT IN ('information_schema', 'pg_catalog')
                    ORDER BY ordinal_position
                """, (table_name,)).fetchall()

                columns = []
                for i, col in enumerate(cols):
                    columns.append({
                        "column_name": col[0],
                        "data_type": col[1],
                        "is_nullable": col[2] == "YES",
                        "is_primary_key": False,
                        "default_value": col[3] or None,
                        "ordinal_position": i + 1,
                        "description": "",
                    })

                tables_data.append({
                    "table_name": table_name,
                    "table_type": table_type,
                    "columns": columns,
                    "row_count": None,
                    "description": "",
                })

            conn.close()
        else:
            update_database_schema_status(db_id, "error")
            raise HTTPException(400, f"Schema import not supported for type: {entry['type']}")

        save_imported_schema(db_id, tables_data)
        update_database_schema_status(db_id, "imported")

        tables_count = len(tables_data)
        columns_count = sum(len(t["columns"]) for t in tables_data)
        logger.info(f"Schema imported: {tables_count} tables, {columns_count} columns")

        from ..admin_config.service import log_database_change
        log_database_change(
            _admin["username"],
            f"导入数据库 Schema: {entry['name']} → {tables_count} 张表，{columns_count} 个字段",
        )

        return {
            "ok": True,
            "tables_count": tables_count,
            "columns_count": columns_count,
            "message": f"已导入 {tables_count} 张表，{columns_count} 个字段",
        }
    except HTTPException:
        raise
    except Exception as e:
        update_database_schema_status(db_id, "error")
        logger.error(f"Schema import failed: {e}")
        raise HTTPException(500, f"Schema import failed: {e}")


@router.get("/api/database/{db_id}/schema")
async def get_imported_schema(db_id: str):
    """Get the imported schema (tables + columns with descriptions) for a database."""
    logger.info(f"GET /api/database/{db_id}/schema")

    entry = next((d for d in state._db_connections if d["id"] == db_id), None)
    if not entry:
        raise HTTPException(404, f"Database '{db_id}' not found")

    tables = load_full_schema(db_id)
    return {"tables": tables}


@router.get("/api/database/{db_id}/schema/status")
async def get_schema_status_endpoint(db_id: str):
    """Get schema import status and description coverage."""
    logger.info(f"GET /api/database/{db_id}/schema/status")

    entry = next((d for d in state._db_connections if d["id"] == db_id), None)
    if not entry:
        raise HTTPException(404, f"Database '{db_id}' not found")

    status = get_schema_status(db_id)
    return SchemaStatusResponse(**status)


@router.post("/api/database/{db_id}/schema/describe")
async def generate_descriptions(db_id: str, req: DescriptionGenerateRequest, _admin: dict = Depends(require_admin)):
    """Use Agent to generate Chinese descriptions for tables and columns."""
    logger.info(f"POST /api/database/{db_id}/schema/describe")

    entry = next((d for d in state._db_connections if d["id"] == db_id), None)
    if not entry:
        raise HTTPException(404, f"Database '{db_id}' not found")

    if not state.config.llm.api_key:
        raise HTTPException(400, "LLM 未配置，无法生成描述")

    from ..agent.describe_schema_agent import generate_descriptions as agent_generate

    try:
        result = await agent_generate(
            database_id=db_id,
            table_ids=req.table_ids,
            language=req.language or "zh",
            force=req.force or False,
        )
        tables_described = result.get("tables_count", 0)
        columns_described = result.get("columns_count", 0)

        from ..admin_config.service import log_database_change
        log_database_change(
            _admin["username"],
            f"AI 生成描述: {entry['name']} → {tables_described} 张表",
        )

        return {
            "ok": True,
            "tables_described": tables_described,
            "columns_described": columns_described,
            "message": f"已为 {tables_described} 张表生成描述",
        }
    except Exception as e:
        logger.error(f"Description generation failed: {e}")
        raise HTTPException(500, f"生成描述失败: {e}")


@router.patch("/api/database/{db_id}/schema/describe")
async def update_description_endpoint(db_id: str, req: DescriptionUpdateRequest, _admin: dict = Depends(require_admin)):
    """Manually update the description of a table or column."""
    logger.info(f"PATCH /api/database/{db_id}/schema/describe")

    entry = next((d for d in state._db_connections if d["id"] == db_id), None)
    if not entry:
        raise HTTPException(404, f"Database '{db_id}' not found")

    if not req.table_id and not req.column_id:
        raise HTTPException(400, "Must provide either table_id or column_id")

    update_description(
        table_id=req.table_id,
        column_id=req.column_id,
        description=req.description,
        description_en=req.description_en,
    )

    target_name = req.table_id or req.column_id or ""
    from ..admin_config.service import log_database_change
    log_database_change(
        _admin["username"],
        f"更新描述: {entry['name']} → {'表' if req.table_id else '字段'} {target_name}",
    )

    return {"ok": True, "message": "描述已更新"}


def _should_exclude(table_name: str, include_patterns: list[str] | None, exclude_patterns: list[str] | None) -> bool:
    """Check if a table should be excluded based on include/exclude patterns."""
    if exclude_patterns:
        for p in exclude_patterns:
            if p.endswith("*") and table_name.startswith(p[:-1]):
                return True
            if fnmatch.fnmatch(table_name, p):
                return True
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
            return True
    return False
