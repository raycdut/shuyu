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
