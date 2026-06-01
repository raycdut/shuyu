"""PostgreSQL connector — remote database via psycopg2."""

from __future__ import annotations

import logging

import psycopg2
import psycopg2.extras

from .base import ColumnInfo, DatabaseConnector, QueryResult, TableInfo

logger = logging.getLogger("shuyu.db")


class PostgreSQLConnector(DatabaseConnector):
    """Connector for PostgreSQL databases using psycopg2."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5432,
        user: str = "postgres",
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
        self._conn: psycopg2.connection | None = None

    def connect(self) -> None:
        logger.info(f"Connecting to PostgreSQL: {self.host}:{self.port}/{self.database}")
        self._conn = psycopg2.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            dbname=self.database,
        )
        self._conn.autocommit = True
        logger.info("PostgreSQL connected")

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def test_connection(self) -> bool:
        try:
            self._ensure_connected()
            with self._conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            return True
        except Exception:
            return False

    def get_schema(self) -> list[TableInfo]:
        self._ensure_connected()
        tables = []

        with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT table_name, table_type
                FROM information_schema.tables
                WHERE table_catalog = %s
                  AND table_schema = 'public'
                  AND table_type IN ('BASE TABLE', 'VIEW')
                ORDER BY table_name
            """, (self.database,))
            rows = cur.fetchall()

            for row in rows:
                table_name = row["table_name"]
                if self._should_exclude(table_name):
                    continue

                cur.execute("""
                    SELECT c.column_name, c.data_type, c.is_nullable,
                           c.character_maximum_length,
                           COALESCE(tc.constraint_type, '') AS constraint_type
                    FROM information_schema.columns c
                    LEFT JOIN information_schema.key_column_usage kcu
                        ON c.table_catalog = kcu.table_catalog
                        AND c.table_schema = kcu.table_schema
                        AND c.table_name = kcu.table_name
                        AND c.column_name = kcu.column_name
                    LEFT JOIN information_schema.table_constraints tc
                        ON kcu.constraint_name = tc.constraint_name
                        AND kcu.table_schema = tc.table_schema
                        AND tc.constraint_type = 'PRIMARY KEY'
                    WHERE c.table_catalog = %s
                      AND c.table_schema = 'public'
                      AND c.table_name = %s
                    ORDER BY c.ordinal_position
                """, (self.database, table_name))
                cols = cur.fetchall()

                columns = []
                for col in cols:
                    col_name = col["column_name"]
                    data_type = col["data_type"]
                    is_nullable = col["is_nullable"]
                    char_length = col["character_maximum_length"]
                    is_pk = col["constraint_type"] == "PRIMARY KEY"

                    data_type_str = self._format_data_type(data_type, char_length)
                    columns.append(ColumnInfo(
                        name=col_name,
                        data_type=data_type_str,
                        is_nullable=is_nullable == "YES",
                        is_primary_key=is_pk,
                        comment="",
                    ))

                tables.append(TableInfo(name=table_name, columns=columns))

        return tables

    def execute(self, sql: str, params: list | None = None, max_rows: int = 1000) -> QueryResult:
        self._ensure_connected()
        with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)

            # For non-query statements, description is None
            if cur.description is None:
                return QueryResult(columns=[], rows=[])

            columns = [desc.name for desc in cur.description]
            rows = cur.fetchmany(max_rows)

            # Convert RealDictCursor rows to ordered lists
            rows_list = [[row[col] for col in columns] for row in rows]

            row_count = len(rows_list)
            stripped = sql.strip().rstrip(";")
            if ";" not in stripped and sql.strip().upper().startswith("SELECT"):
                try:
                    cur.execute(f"SELECT COUNT(*) AS cnt FROM ({sql}) AS _sub")
                    count_result = cur.fetchone()
                    if count_result:
                        row_count = count_result["cnt"]
                except Exception:
                    pass

        return QueryResult(columns=columns, rows=rows_list, row_count=row_count)

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
    def _format_data_type(data_type: str, char_length: int | None) -> str:
        if char_length and data_type in ("character varying", "varchar", "character", "char"):
            return f"{data_type}({char_length})"
        return data_type
