"""MySQL connector — remote database via PyMySQL."""

from __future__ import annotations

import logging

import pymysql

from .base import ColumnInfo, DatabaseConnector, QueryResult, TableInfo

logger = logging.getLogger("shuyu.db")


class MySQLConnector(DatabaseConnector):
    """Connector for MySQL databases using PyMySQL."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 3306,
        user: str = "root",
        password: str = "",
        database: str = "",
        include_tables: list[str] = None,
        exclude_tables: list[str] = None,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.include_tables = include_tables
        self.exclude_tables = exclude_tables or []
        self._conn: pymysql.Connection | None = None

    def connect(self) -> None:
        logger.info(f"Connecting to MySQL: {self.host}:{self.port}/{self.database}")
        self._conn = pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.Cursor,
        )
        logger.info("MySQL connected")

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def test_connection(self) -> bool:
        try:
            self._ensure_connected()
            with self._conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            return False

    def get_schema(self) -> list[TableInfo]:
        self._ensure_connected()
        tables = []

        with self._conn.cursor() as cursor:
            cursor.execute("""
                SELECT table_name, table_type
                FROM information_schema.tables
                WHERE table_schema = %s
                ORDER BY table_name
            """, (self.database,))
            rows = cursor.fetchall()

            for table_name, table_type in rows:
                if self._should_exclude(table_name):
                    continue

                cursor.execute("""
                    SELECT column_name, data_type, is_nullable,
                           COALESCE(column_default, '') as column_default,
                           COALESCE(character_maximum_length, 0) as char_length,
                           column_key
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                """, (self.database, table_name))
                cols = cursor.fetchall()

                columns = []
                for col in cols:
                    col_name, data_type, is_nullable, default, char_length, col_key = col
                    data_type_str = self._format_data_type(data_type, char_length)
                    columns.append(ColumnInfo(
                        name=col_name,
                        data_type=data_type_str,
                        is_nullable=is_nullable == "YES",
                        is_primary_key=col_key == "PRI",
                        comment="",
                    ))

                tables.append(TableInfo(name=table_name, columns=columns))

        return tables

    def execute(self, sql: str, params: list | None = None, max_rows: int = 1000) -> QueryResult:
        self._ensure_connected()
        with self._conn.cursor() as cursor:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)

            # For non-query statements, description is None
            if cursor.description is None:
                self._conn.commit()
                return QueryResult(columns=[], rows=[])

            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchmany(max_rows)

            # Count total rows if possible (safety: only single-statement)
            row_count = len(rows)
            stripped = sql.strip().rstrip(";")
            if ";" not in stripped and sql.strip().upper().startswith("SELECT"):
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM ({sql}) AS _sub")
                    count_result = cursor.fetchone()
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
            return True

        return False

    @staticmethod
    def _format_data_type(data_type: str, char_length: int) -> str:
        if char_length and data_type in ("varchar", "char"):
            return f"{data_type}({char_length})"
        return data_type
