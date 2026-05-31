"""Persistence — imported tables and columns (schema management)."""

from __future__ import annotations

import json
import time
import uuid

from .. import state


def load_imported_tables(database_id: str) -> list[dict]:
    """Load all imported tables for a given database."""
    sql = state._sqlite
    if sql is None:
        return []
    rows = sql.execute(
        "SELECT id, database_id, table_name, table_type, row_count, description, "
        "description_en, raw_ddl, created_at, updated_at "
        "FROM imported_tables WHERE database_id = ? ORDER BY table_name",
        (database_id,),
    ).fetchall()
    return [
        {
            "id": r[0], "database_id": r[1], "table_name": r[2],
            "table_type": r[3], "row_count": r[4], "description": r[5] or "",
            "description_en": r[6] or "", "raw_ddl": r[7],
            "created_at": r[8], "updated_at": r[9],
        }
        for r in rows
    ]


def load_imported_columns(table_id: str) -> list[dict]:
    """Load all imported columns for a given table."""
    sql = state._sqlite
    if sql is None:
        return []
    rows = sql.execute(
        "SELECT id, table_id, column_name, data_type, is_nullable, is_primary_key, "
        "default_value, ordinal_position, description, sample_values, created_at, updated_at "
        "FROM imported_columns WHERE table_id = ? ORDER BY ordinal_position",
        (table_id,),
    ).fetchall()
    result = []
    for r in rows:
        sample = json.loads(r[9]) if r[9] else None
        result.append({
            "id": r[0], "table_id": r[1], "column_name": r[2],
            "data_type": r[3], "is_nullable": bool(r[4]),
            "is_primary_key": bool(r[5]), "default_value": r[6],
            "ordinal_position": r[7], "description": r[8] or "",
            "sample_values": sample,
            "created_at": r[10], "updated_at": r[11],
        })
    return result


def load_full_schema(database_id: str) -> list[dict]:
    """Load all imported tables with their columns for a database."""
    tables = load_imported_tables(database_id)
    for t in tables:
        t["columns"] = load_imported_columns(t["id"])
    return tables


def delete_imported_schema(database_id: str) -> None:
    """Delete all imported tables and columns for a database (cascade)."""
    sql = state._sqlite
    if sql is None:
        return
    sql.execute("DELETE FROM imported_tables WHERE database_id = ?", (database_id,))
    sql.commit()


def save_imported_schema(database_id: str, tables: list[dict]) -> None:
    """Save imported tables and columns, replacing any existing data."""
    sql = state._sqlite
    if sql is None:
        return

    delete_imported_schema(database_id)

    now = time.time()
    for t in tables:
        table_id = str(uuid.uuid4())[:8]
        sql.execute(
            "INSERT INTO imported_tables "
            "(id, database_id, table_name, table_type, row_count, description, "
            "description_en, raw_ddl, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                table_id, database_id, t["table_name"], t.get("table_type", "TABLE"),
                t.get("row_count"), t.get("description", ""),
                t.get("description_en", ""), t.get("raw_ddl"),
                now, now,
            ),
        )
        for col in t.get("columns", []):
            col_id = str(uuid.uuid4())[:8]
            sample_json = json.dumps(col.get("sample_values")) if col.get("sample_values") else None
            sql.execute(
                "INSERT INTO imported_columns "
                "(id, table_id, column_name, data_type, is_nullable, is_primary_key, "
                "default_value, ordinal_position, description, sample_values, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    col_id, table_id, col["column_name"], col["data_type"],
                    1 if col.get("is_nullable", True) else 0,
                    1 if col.get("is_primary_key", False) else 0,
                    col.get("default_value"), col.get("ordinal_position", 0),
                    col.get("description", ""), sample_json,
                    now, now,
                ),
            )
    sql.commit()


def update_description(
    table_id: str | None = None,
    column_id: str | None = None,
    description: str = "",
) -> None:
    """Update the description of a table or column."""
    sql = state._sqlite
    if sql is None:
        return
    now = time.time()
    if table_id:
        sql.execute(
            "UPDATE imported_tables SET description = ?, updated_at = ? WHERE id = ?",
            (description, now, table_id),
        )
    elif column_id:
        sql.execute(
            "UPDATE imported_columns SET description = ?, updated_at = ? WHERE id = ?",
            (description, now, column_id),
        )
    sql.commit()


def update_database_schema_status(database_id: str, status: str) -> None:
    """Update the schema_status of a database."""
    sql = state._sqlite
    if sql is None:
        return
    sql.execute(
        "UPDATE databases SET schema_status = ? WHERE id = ?",
        (status, database_id),
    )
    sql.commit()


def get_schema_status(database_id: str) -> dict:
    """Get schema import status and description coverage stats."""
    sql = state._sqlite
    if sql is None:
        return {"schema_status": "pending", "tables_count": 0, "columns_count": 0,
                "described_tables": 0, "described_columns": 0}

    db_row = sql.execute(
        "SELECT schema_status FROM databases WHERE id = ?", (database_id,)
    ).fetchone()
    status = db_row[0] if db_row and db_row[0] else "pending"

    tables = load_imported_tables(database_id)
    tables_count = len(tables)
    columns_count = 0
    described_tables = 0
    described_columns = 0

    for t in tables:
        cols = load_imported_columns(t["id"])
        columns_count += len(cols)
        if t.get("description"):
            described_tables += 1
        for c in cols:
            if c.get("description"):
                described_columns += 1

    return {
        "schema_status": status,
        "tables_count": tables_count,
        "columns_count": columns_count,
        "described_tables": described_tables,
        "described_columns": described_columns,
    }


def save_descriptions(database_id: str, descriptions: list[dict]) -> int:
    """Save descriptions generated by Agent.

    Args:
        database_id: Target database ID.
        descriptions: List of dicts with keys:
            - table_name: str
            - table_description: str
            - columns: list[dict] with column_name and column_description

    Returns:
        Number of tables updated.
    """
    sql = state._sqlite
    if sql is None:
        return 0

    now = time.time()
    count = 0

    for desc in descriptions:
        table_name = desc.get("table_name", "")
        table_desc = desc.get("table_description", "")

        tbl = sql.execute(
            "SELECT id FROM imported_tables WHERE database_id = ? AND table_name = ?",
            (database_id, table_name),
        ).fetchone()
        if not tbl:
            continue

        table_id = tbl[0]
        if table_desc:
            sql.execute(
                "UPDATE imported_tables SET description = ?, updated_at = ? WHERE id = ?",
                (table_desc, now, table_id),
            )
            count += 1

        cols = desc.get("columns", [])
        for col_desc in cols:
            col_name = col_desc.get("column_name", "")
            col_desc_text = col_desc.get("column_description", "")
            if not col_desc_text:
                continue

            col = sql.execute(
                "SELECT id FROM imported_columns WHERE table_id = ? AND column_name = ?",
                (table_id, col_name),
            ).fetchone()
            if col:
                sql.execute(
                    "UPDATE imported_columns SET description = ?, updated_at = ? WHERE id = ?",
                    (col_desc_text, now, col[0]),
                )

    sql.commit()
    return count
