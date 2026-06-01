"""Persistence — imported tables and columns via SQLAlchemy ORM."""

from __future__ import annotations

import json
import time
import uuid

from .. import state
from ..configdb.base import scoped_session
from ..configdb.models.database import DatabaseConnection as DatabaseConnectionModel
from ..configdb.models.schema import ImportedTable, ImportedColumn


def load_imported_tables(database_id: str) -> list[dict]:
    """Load all imported tables for a given database."""
    try:
        with scoped_session() as session:
            rows = session.query(ImportedTable).filter_by(
                database_id=database_id
            ).order_by(ImportedTable.table_name).all()
            return [
                {
                    "id": r.id,
                    "database_id": r.database_id,
                    "table_name": r.table_name,
                    "table_type": r.table_type,
                    "row_count": r.row_count,
                    "description": r.description or "",
                    "description_en": r.description_en or "",
                    "raw_ddl": r.raw_ddl,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
                for r in rows
            ]
    except Exception:
        return []


def load_imported_columns(table_id: str) -> list[dict]:
    """Load all imported columns for a given table."""
    try:
        with scoped_session() as session:
            rows = session.query(ImportedColumn).filter_by(
                table_id=table_id
            ).order_by(ImportedColumn.ordinal_position).all()
            result = []
            for r in rows:
                sample = json.loads(r.sample_values) if r.sample_values else None
                result.append({
                    "id": r.id,
                    "table_id": r.table_id,
                    "column_name": r.column_name,
                    "data_type": r.data_type,
                    "is_nullable": bool(r.is_nullable),
                    "is_primary_key": bool(r.is_primary_key),
                    "default_value": r.default_value,
                    "ordinal_position": r.ordinal_position,
                    "description": r.description or "",
                    "description_en": r.description_en or "",
                    "sample_values": sample,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                })
            return result
    except Exception:
        return []


def load_full_schema(database_id: str) -> list[dict]:
    """Load all imported tables with their columns for a database."""
    tables = load_imported_tables(database_id)
    for t in tables:
        t["columns"] = load_imported_columns(t["id"])
    return tables


def delete_imported_schema(database_id: str) -> None:
    """Delete all imported tables and columns for a database (cascade)."""
    try:
        with scoped_session() as session:
            session.query(ImportedTable).filter_by(database_id=database_id).delete()
    except Exception:
        pass


def save_imported_schema(database_id: str, tables: list[dict]) -> None:
    """Save imported tables and columns, replacing any existing data."""
    try:
        with scoped_session() as session:
            # Delete existing
            session.query(ImportedTable).filter_by(database_id=database_id).delete()
            now = time.time()
            for t in tables:
                table_id = str(uuid.uuid4())[:8]
                tbl = ImportedTable(
                    id=table_id,
                    database_id=database_id,
                    table_name=t["table_name"],
                    table_type=t.get("table_type", "TABLE"),
                    row_count=t.get("row_count"),
                    description=t.get("description", ""),
                    description_en=t.get("description_en", ""),
                    raw_ddl=t.get("raw_ddl"),
                    created_at=now,
                    updated_at=now,
                )
                session.add(tbl)
                for col in t.get("columns", []):
                    col_id = str(uuid.uuid4())[:8]
                    sample_json = json.dumps(col.get("sample_values")) if col.get("sample_values") else None
                    session.add(ImportedColumn(
                        id=col_id,
                        table_id=table_id,
                        column_name=col["column_name"],
                        data_type=col["data_type"],
                        is_nullable=1 if col.get("is_nullable", True) else 0,
                        is_primary_key=1 if col.get("is_primary_key", False) else 0,
                        default_value=col.get("default_value"),
                        ordinal_position=col.get("ordinal_position", 0),
                        description=col.get("description", ""),
                        description_en=col.get("description_en", ""),
                        sample_values=sample_json,
                        created_at=now,
                        updated_at=now,
                    ))
    except Exception:
        pass


def update_description(
    table_id: str | None = None,
    column_id: str | None = None,
    description: str = "",
    description_en: str = "",
) -> None:
    """Update the description (and optional English description) of a table or column."""
    try:
        with scoped_session() as session:
            now = time.time()
            if table_id:
                session.query(ImportedTable).filter_by(id=table_id).update({
                    "description": description,
                    "description_en": description_en,
                    "updated_at": now,
                })
            elif column_id:
                session.query(ImportedColumn).filter_by(id=column_id).update({
                    "description": description,
                    "description_en": description_en,
                    "updated_at": now,
                })
    except Exception:
        pass


def update_database_schema_status(database_id: str, status: str) -> None:
    """Update the schema_status of a database."""
    try:
        with scoped_session() as session:
            session.query(DatabaseConnectionModel).filter_by(id=database_id).update({
                "schema_status": status,
            })
    except Exception:
        pass


def get_schema_status(database_id: str) -> dict:
    """Get schema import status and description coverage stats."""
    try:
        with scoped_session() as session:
            db_row = session.query(DatabaseConnectionModel).filter_by(id=database_id).first()
            status = db_row.schema_status if db_row and db_row.schema_status else "pending"

            tables = session.query(ImportedTable).filter_by(database_id=database_id).all()
            tables_count = len(tables)
            columns_count = 0
            described_tables = 0
            described_columns = 0

            for t in tables:
                cols = session.query(ImportedColumn).filter_by(table_id=t.id).all()
                columns_count += len(cols)
                if t.description:
                    described_tables += 1
                for c in cols:
                    if c.description:
                        described_columns += 1

            return {
                "schema_status": status,
                "tables_count": tables_count,
                "columns_count": columns_count,
                "described_tables": described_tables,
                "described_columns": described_columns,
            }
    except Exception:
        return {
            "schema_status": "pending",
            "tables_count": 0,
            "columns_count": 0,
            "described_tables": 0,
            "described_columns": 0,
        }


def save_descriptions(database_id: str, descriptions: list[dict]) -> int:
    """Save descriptions generated by Agent.

    Args:
        database_id: Target database ID.
        descriptions: List of dicts with keys:
            - table_name: str
            - table_description: str
            - table_description_en: str (optional)
            - columns: list[dict] with column_name, column_description, column_description_en (optional)

    Returns:
        Number of tables updated.
    """
    count = 0
    try:
        with scoped_session() as session:
            now = time.time()
            for desc in descriptions:
                table_name = desc.get("table_name", "")
                table_desc = desc.get("table_description", "")
                table_desc_en = desc.get("table_description_en", "")

                tbl = session.query(ImportedTable).filter_by(
                    database_id=database_id, table_name=table_name
                ).first()
                if not tbl:
                    continue

                if table_desc or table_desc_en:
                    tbl.description = table_desc
                    tbl.description_en = table_desc_en
                    tbl.updated_at = now
                    count += 1

                cols = desc.get("columns", [])
                for col_desc in cols:
                    col_name = col_desc.get("column_name", "")
                    col_desc_text = col_desc.get("column_description", "")
                    col_desc_en = col_desc.get("column_description_en", "")
                    if not col_desc_text and not col_desc_en:
                        continue

                    col = session.query(ImportedColumn).filter_by(
                        table_id=tbl.id, column_name=col_name
                    ).first()
                    if col:
                        col.description = col_desc_text
                        col.description_en = col_desc_en
                        col.updated_at = now

            return count
    except Exception:
        return count
