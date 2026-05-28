"""DuckDB connector — local file-based database."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

from .base import ColumnInfo, DatabaseConnector, QueryResult, TableInfo

logger = logging.getLogger("shuyu.db")


class DuckDBConnector(DatabaseConnector):
    def __init__(self, db_path: str = "./data/analytics.db", include_tables: list[str] = None, exclude_tables: list[str] = None):
        self.db_path = db_path
        self.include_tables = include_tables
        self.exclude_tables = exclude_tables or []
        self._conn: duckdb.DuckDBPyConnection | None = None

    def connect(self) -> None:
        logger.info(f"Connecting to DuckDB: {self.db_path}")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(self.db_path)
        logger.info("DuckDB connected")

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def test_connection(self) -> bool:
        try:
            self._ensure_connected()
            self._conn.execute("SELECT 1").fetchone()  # type: ignore
            return True
        except Exception:
            return False

    def get_schema(self) -> list[TableInfo]:
        self._ensure_connected()
        tables = []

        # Get all tables and views
        rows = self._conn.execute("""
            SELECT table_name, table_type
            FROM information_schema.tables
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY table_name
        """).fetchall()  # type: ignore

        for table_name, table_type in rows:
            if self._should_exclude(table_name):
                continue

            # Get columns for this table
            cols = self._conn.execute(f"""
                SELECT column_name, data_type, is_nullable,
                       COALESCE(column_default, '') as column_default
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
                  AND table_schema NOT IN ('information_schema', 'pg_catalog')
                ORDER BY ordinal_position
            """).fetchall()  # type: ignore

            columns = [
                ColumnInfo(
                    name=col[0],
                    data_type=col[1],
                    is_nullable=col[2] == "YES",
                    comment="",
                )
                for col in cols
            ]

            tables.append(TableInfo(name=table_name, columns=columns))

        return tables

    def execute(self, sql: str, params: list | None = None, max_rows: int = 1000) -> QueryResult:
        """Execute a SQL query with optional parameters.

        Args:
            sql: SQL statement (SELECT) or DDL/DML.
            params: Optional parameter list for parameterized queries.
            max_rows: Max rows to fetch for SELECT queries.
        """
        self._ensure_connected()
        if params:
            result = self._conn.execute(sql, params)  # type: ignore
        else:
            result = self._conn.execute(sql)  # type: ignore

        # For non-query statements (INSERT/UPDATE/CREATE), description is None
        if result.description is None:
            return QueryResult(columns=[], rows=[])

        columns = [desc[0] for desc in result.description]
        rows = result.fetchmany(max_rows)  # type: ignore

        # Count total rows if possible
        row_count = len(rows)
        try:
            count_result = self._conn.execute(f"SELECT COUNT(*) FROM ({sql}) AS _sub").fetchone()  # type: ignore
            if count_result:
                row_count = count_result[0]
        except Exception:
            pass

        return QueryResult(columns=columns, rows=list(rows), row_count=row_count)

    def _ensure_connected(self) -> None:
        if self._conn is None:
            self.connect()

    def _should_exclude(self, table_name: str) -> bool:
        if self.exclude_tables:
            for pattern in self.exclude_tables:
                if pattern.endswith("*") and table_name.startswith(pattern[:-1]):
                    return True
                if table_name == pattern:
                    return True

        if self.include_tables:
            for pattern in self.include_tables:
                if pattern.endswith("*") and table_name.startswith(pattern[:-1]):
                    return False
                if table_name == pattern:
                    return False
            return True  # Not in include list, exclude

        return False
