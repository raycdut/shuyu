from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class DBConnectRequest(BaseModel):
    name: str = ""
    type: str = "duckdb"
    path: str | None = None
    connection_string: str | None = None
    host: str | None = None
    port: int | None = None
    user: str | None = None
    password: str | None = None
    database: str | None = None
    include_tables: list[str] | None = None
    exclude_tables: list[str] | None = None


class DBInfo(BaseModel):
    id: str
    name: str
    type: str
    connection_string: str | None = None
    include_tables: list[str] | None = None
    exclude_tables: list[str] | None = None
    is_active: bool = False


class DBTestResult(BaseModel):
    ok: bool
    message: str


class ColumnSchema(BaseModel):
    column_name: str
    data_type: str
    is_nullable: bool = True
    is_primary_key: bool = False
    default_value: str | None = None
    ordinal_position: int = 0


class TableSchema(BaseModel):
    table_name: str
    table_type: str = "TABLE"
    columns: list[ColumnSchema]


class ImportedColumnInfo(BaseModel):
    id: str
    column_name: str
    data_type: str
    is_nullable: bool = True
    is_primary_key: bool = False
    description: str = ""
    sample_values: list[str] | None = None


class ImportedTableInfo(BaseModel):
    id: str
    database_id: str
    table_name: str
    table_type: str = "TABLE"
    description: str = ""
    row_count: int | None = None
    columns: list[ImportedColumnInfo] = []
    created_at: float = 0
    updated_at: float = 0


class SchemaImportRequest(BaseModel):
    database_id: str | None = None
    include_tables: list[str] | None = None
    exclude_tables: list[str] | None = None


class DescriptionGenerateRequest(BaseModel):
    table_ids: list[str] | None = None
    language: str = "zh"
    force: bool = False


class DescriptionUpdateRequest(BaseModel):
    table_id: str | None = None
    column_id: str | None = None
    description: str


class SchemaStatusResponse(BaseModel):
    schema_status: str = "pending"
    tables_count: int = 0
    columns_count: int = 0
    described_tables: int = 0
    described_columns: int = 0
