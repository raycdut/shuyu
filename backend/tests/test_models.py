from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.chat import ChatRequest, ChatResponse
from app.models.session import SessionRenameRequest, SessionMessagesResponse
from app.models.config import ConfigUpdate, LLMTestResult
from app.models.database import (
    DBConnectRequest,
    DBInfo,
    DBTestResult,
    ColumnSchema,
    TableSchema,
    ImportedColumnInfo,
    ImportedTableInfo,
    SchemaImportRequest,
    DescriptionGenerateRequest,
    DescriptionUpdateRequest,
    SchemaStatusResponse,
)


class TestChatRequest:
    """Tests for ChatRequest model."""

    def test_minimal_request(self):
        """Should create a ChatRequest with only the required message field."""
        req = ChatRequest(message="Hello")
        assert req.message == "Hello"
        assert req.session_id is None
        assert req.db_id is None
        assert req.mode == "fast"

    def test_with_all_fields(self):
        """Should create a ChatRequest with all fields provided."""
        req = ChatRequest(
            message="Show me data",
            session_id="sess-123",
            db_id="db-456",
            mode="quality",
        )
        assert req.message == "Show me data"
        assert req.session_id == "sess-123"
        assert req.db_id == "db-456"
        assert req.mode == "quality"

    def test_with_partial_optional_fields(self):
        """Should create a ChatRequest with only some optional fields."""
        req = ChatRequest(message="Hi", session_id="sess-1")
        assert req.message == "Hi"
        assert req.session_id == "sess-1"
        assert req.db_id is None
        assert req.mode == "fast"

    def test_default_mode_is_fast(self):
        """Should default to 'fast' mode when not specified."""
        req = ChatRequest(message="Test")
        assert req.mode == "fast"

    def test_empty_message_is_allowed(self):
        """Should allow an empty string for message since Pydantic v2 does not enforce non-empty by default."""
        req = ChatRequest(message="")
        assert req.message == ""

    def test_mode_can_be_custom(self):
        """Should accept custom mode strings beyond 'fast' and 'quality'."""
        req = ChatRequest(message="Test", mode="custom")
        assert req.mode == "custom"


class TestChatResponse:
    """Tests for ChatResponse model."""

    def test_minimal_response(self):
        """Should create a ChatResponse with only required fields."""
        resp = ChatResponse(reply="Hello back", session_id="sess-1")
        assert resp.reply == "Hello back"
        assert resp.session_id == "sess-1"
        assert resp.tool_calls == []
        assert resp.sql_queries == []
        assert resp.query_results == []

    def test_with_all_fields(self):
        """Should create a ChatResponse with all fields provided."""
        resp = ChatResponse(
            reply="Result",
            session_id="sess-1",
            tool_calls=[{"name": "query", "args": {"sql": "SELECT 1"}}],
            sql_queries=["SELECT 1"],
            query_results=[{"col": "val"}],
        )
        assert resp.reply == "Result"
        assert resp.tool_calls == [{"name": "query", "args": {"sql": "SELECT 1"}}]
        assert resp.sql_queries == ["SELECT 1"]
        assert resp.query_results == [{"col": "val"}]

    def test_default_tool_calls_is_empty_list(self):
        """Should default tool_calls to an empty list."""
        resp = ChatResponse(reply="Hi", session_id="sess-1")
        assert resp.tool_calls == []

    def test_default_sql_queries_is_empty_list(self):
        """Should default sql_queries to an empty list."""
        resp = ChatResponse(reply="Hi", session_id="sess-1")
        assert resp.sql_queries == []

    def test_default_query_results_is_empty_list(self):
        """Should default query_results to an empty list."""
        resp = ChatResponse(reply="Hi", session_id="sess-1")
        assert resp.query_results == []

    def test_missing_reply_raises_error(self):
        """Should raise ValidationError when reply is missing."""
        with pytest.raises(ValidationError):
            ChatResponse(session_id="sess-1")

    def test_missing_session_id_raises_error(self):
        """Should raise ValidationError when session_id is missing."""
        with pytest.raises(ValidationError):
            ChatResponse(reply="Hi")


class TestSessionRenameRequest:
    """Tests for SessionRenameRequest model."""

    def test_create_with_title(self):
        """Should create a SessionRenameRequest with a title."""
        req = SessionRenameRequest(title="New Title")
        assert req.title == "New Title"

    def test_empty_title(self):
        """Should create a SessionRenameRequest with an empty title string."""
        req = SessionRenameRequest(title="")
        assert req.title == ""

    def test_missing_title_raises_error(self):
        """Should raise ValidationError when title is missing."""
        with pytest.raises(ValidationError):
            SessionRenameRequest()


class TestSessionMessagesResponse:
    """Tests for SessionMessagesResponse model."""

    def test_create_with_fields(self):
        """Should create a SessionMessagesResponse with session_id and messages."""
        resp = SessionMessagesResponse(
            session_id="sess-1",
            messages=[{"role": "user", "content": "Hi"}],
        )
        assert resp.session_id == "sess-1"
        assert resp.messages == [{"role": "user", "content": "Hi"}]

    def test_empty_messages(self):
        """Should create a SessionMessagesResponse with an empty messages list."""
        resp = SessionMessagesResponse(session_id="sess-1", messages=[])
        assert resp.messages == []

    def test_missing_session_id_raises_error(self):
        """Should raise ValidationError when session_id is missing."""
        with pytest.raises(ValidationError):
            SessionMessagesResponse(messages=[])

    def test_missing_messages_raises_error(self):
        """Should raise ValidationError when messages is missing."""
        with pytest.raises(ValidationError):
            SessionMessagesResponse(session_id="sess-1")


class TestConfigUpdate:
    """Tests for ConfigUpdate model."""

    def test_empty_update(self):
        """Should create a ConfigUpdate with no fields set."""
        update = ConfigUpdate()
        assert update.llm is None
        assert update.safety is None

    def test_with_llm_only(self):
        """Should create a ConfigUpdate with only llm field."""
        update = ConfigUpdate(llm={"model": "gpt-4", "temperature": 0.5})
        assert update.llm == {"model": "gpt-4", "temperature": 0.5}
        assert update.safety is None

    def test_with_safety_only(self):
        """Should create a ConfigUpdate with only safety field."""
        update = ConfigUpdate(safety={"max_tokens": 4096, "rate_limit": 100})
        assert update.safety == {"max_tokens": 4096, "rate_limit": 100}
        assert update.llm is None

    def test_with_both_fields(self):
        """Should create a ConfigUpdate with both llm and safety fields."""
        update = ConfigUpdate(
            llm={"model": "gpt-4"},
            safety={"rate_limit": 50},
        )
        assert update.llm == {"model": "gpt-4"}
        assert update.safety == {"rate_limit": 50}

    def test_with_nested_dict(self):
        """Should accept complex nested dictionaries in llm or safety."""
        update = ConfigUpdate(
            llm={"providers": {"openai": {"api_key": "test"}}},
        )
        assert update.llm["providers"]["openai"]["api_key"] == "test"


class TestLLMTestResult:
    """Tests for LLMTestResult model."""

    def test_success_result(self):
        """Should create a successful LLMTestResult."""
        result = LLMTestResult(ok=True, message="Connection successful")
        assert result.ok is True
        assert result.message == "Connection successful"

    def test_failure_result(self):
        """Should create a failed LLMTestResult."""
        result = LLMTestResult(ok=False, message="Connection failed")
        assert result.ok is False
        assert result.message == "Connection failed"

    def test_empty_message(self):
        """Should create an LLMTestResult with an empty message."""
        result = LLMTestResult(ok=True, message="")
        assert result.ok is True
        assert result.message == ""

    def test_missing_ok_raises_error(self):
        """Should raise ValidationError when ok is missing."""
        with pytest.raises(ValidationError):
            LLMTestResult(message="test")

    def test_missing_message_raises_error(self):
        """Should raise ValidationError when message is missing."""
        with pytest.raises(ValidationError):
            LLMTestResult(ok=True)


class TestDBConnectRequest:
    """Tests for DBConnectRequest model."""

    def test_minimal_request(self):
        """Should create a DBConnectRequest with defaults only."""
        req = DBConnectRequest()
        assert req.name == ""
        assert req.type == "duckdb"
        assert req.path is None
        assert req.connection_string is None
        assert req.host is None
        assert req.port is None
        assert req.user is None
        assert req.password is None
        assert req.database is None
        assert req.include_tables is None
        assert req.exclude_tables is None

    def test_with_mysql_connection(self):
        """Should create a DBConnectRequest for MySQL with host and port."""
        req = DBConnectRequest(
            name="My MySQL",
            type="mysql",
            host="localhost",
            port=3306,
            user="root",
            password="secret",
            database="testdb",
        )
        assert req.name == "My MySQL"
        assert req.type == "mysql"
        assert req.host == "localhost"
        assert req.port == 3306
        assert req.user == "root"
        assert req.password == "secret"
        assert req.database == "testdb"

    def test_with_file_path(self):
        """Should create a DBConnectRequest with a file path for DuckDB."""
        req = DBConnectRequest(
            name="Local DB",
            type="duckdb",
            path="/data/db.duckdb",
        )
        assert req.path == "/data/db.duckdb"
        assert req.type == "duckdb"

    def test_with_connection_string(self):
        """Should create a DBConnectRequest with a connection string."""
        req = DBConnectRequest(
            name="Remote DB",
            type="postgresql",
            connection_string="postgresql://user:pass@host:5432/db",
        )
        assert req.connection_string == "postgresql://user:pass@host:5432/db"

    def test_with_include_exclude_tables(self):
        """Should create a DBConnectRequest with include/exclude table lists."""
        req = DBConnectRequest(
            name="Filtered DB",
            type="duckdb",
            include_tables=["users", "orders"],
            exclude_tables=["logs"],
        )
        assert req.include_tables == ["users", "orders"]
        assert req.exclude_tables == ["logs"]


class TestDBInfo:
    """Tests for DBInfo model."""

    def test_minimal_dbinfo(self):
        """Should create a DBInfo with only required fields."""
        info = DBInfo(id="db-1", name="Test DB", type="duckdb")
        assert info.id == "db-1"
        assert info.name == "Test DB"
        assert info.type == "duckdb"
        assert info.connection_string is None
        assert info.include_tables is None
        assert info.exclude_tables is None
        assert info.is_active is False

    def test_with_all_fields(self):
        """Should create a DBInfo with all fields."""
        info = DBInfo(
            id="db-1",
            name="Test DB",
            type="postgresql",
            connection_string="postgresql://localhost/db",
            include_tables=["users"],
            exclude_tables=[],
            is_active=True,
        )
        assert info.is_active is True
        assert info.include_tables == ["users"]

    def test_missing_id_raises_error(self):
        """Should raise ValidationError when id is missing."""
        with pytest.raises(ValidationError):
            DBInfo(name="Test", type="duckdb")


class TestDBTestResult:
    """Tests for DBTestResult model."""

    def test_ok_result(self):
        """Should create a successful DBTestResult."""
        result = DBTestResult(ok=True, message="Connected")
        assert result.ok is True
        assert result.message == "Connected"

    def test_fail_result(self):
        """Should create a failed DBTestResult."""
        result = DBTestResult(ok=False, message="Error")
        assert result.ok is False

    def test_missing_ok_raises_error(self):
        """Should raise ValidationError when ok is missing."""
        with pytest.raises(ValidationError):
            DBTestResult(message="no ok field")


class TestColumnSchema:
    """Tests for ColumnSchema model."""

    def test_minimal_column(self):
        """Should create a ColumnSchema with only required fields."""
        col = ColumnSchema(column_name="id", data_type="INTEGER")
        assert col.column_name == "id"
        assert col.data_type == "INTEGER"
        assert col.is_nullable is True
        assert col.is_primary_key is False
        assert col.default_value is None
        assert col.ordinal_position == 0

    def test_with_all_fields(self):
        """Should create a ColumnSchema with all fields."""
        col = ColumnSchema(
            column_name="email",
            data_type="VARCHAR",
            is_nullable=False,
            is_primary_key=False,
            default_value="''",
            ordinal_position=2,
        )
        assert col.is_nullable is False
        assert col.default_value == "''"
        assert col.ordinal_position == 2

    def test_primary_key_column(self):
        """Should create a ColumnSchema marked as primary key."""
        col = ColumnSchema(
            column_name="id",
            data_type="INTEGER",
            is_primary_key=True,
        )
        assert col.is_primary_key is True


class TestTableSchema:
    """Tests for TableSchema model."""

    def test_minimal_table(self):
        """Should create a TableSchema with only required fields."""
        table = TableSchema(
            table_name="users",
            columns=[ColumnSchema(column_name="id", data_type="INTEGER")],
        )
        assert table.table_name == "users"
        assert table.table_type == "TABLE"
        assert len(table.columns) == 1
        assert table.columns[0].column_name == "id"

    def test_view_type(self):
        """Should create a TableSchema with view type."""
        table = TableSchema(
            table_name="user_view",
            table_type="VIEW",
            columns=[],
        )
        assert table.table_type == "VIEW"

    def test_multiple_columns(self):
        """Should create a TableSchema with multiple columns."""
        cols = [
            ColumnSchema(column_name="id", data_type="INTEGER"),
            ColumnSchema(column_name="name", data_type="TEXT"),
            ColumnSchema(column_name="email", data_type="TEXT"),
        ]
        table = TableSchema(table_name="users", columns=cols)
        assert len(table.columns) == 3


class TestImportedColumnInfo:
    """Tests for ImportedColumnInfo model."""

    def test_minimal_imported_column(self):
        """Should create an ImportedColumnInfo with only required fields."""
        col = ImportedColumnInfo(id="col-1", column_name="id", data_type="INTEGER")
        assert col.id == "col-1"
        assert col.column_name == "id"
        assert col.data_type == "INTEGER"
        assert col.is_nullable is True
        assert col.is_primary_key is False
        assert col.description == ""
        assert col.description_en == ""
        assert col.sample_values is None

    def test_with_sample_values(self):
        """Should create an ImportedColumnInfo with sample values."""
        col = ImportedColumnInfo(
            id="col-2",
            column_name="name",
            data_type="TEXT",
            description="用户姓名",
            description_en="User name",
            sample_values=["Alice", "Bob"],
        )
        assert col.sample_values == ["Alice", "Bob"]

    def test_empty_sample_values(self):
        """Should create an ImportedColumnInfo with an empty sample values list."""
        col = ImportedColumnInfo(
            id="col-3",
            column_name="email",
            data_type="TEXT",
            sample_values=[],
        )
        assert col.sample_values == []


class TestImportedTableInfo:
    """Tests for ImportedTableInfo model."""

    def test_minimal_imported_table(self):
        """Should create an ImportedTableInfo with only required fields."""
        table = ImportedTableInfo(id="tbl-1", database_id="db-1", table_name="users")
        assert table.id == "tbl-1"
        assert table.database_id == "db-1"
        assert table.table_name == "users"
        assert table.table_type == "TABLE"
        assert table.description == ""
        assert table.description_en == ""
        assert table.row_count is None
        assert table.columns == []
        assert table.created_at == 0
        assert table.updated_at == 0

    def test_with_columns(self):
        """Should create an ImportedTableInfo with nested columns."""
        cols = [
            ImportedColumnInfo(id="c1", column_name="id", data_type="INTEGER"),
            ImportedColumnInfo(id="c2", column_name="name", data_type="TEXT"),
        ]
        table = ImportedTableInfo(
            id="tbl-1",
            database_id="db-1",
            table_name="users",
            columns=cols,
            row_count=100,
            created_at=1000.0,
            updated_at=2000.0,
        )
        assert len(table.columns) == 2
        assert table.row_count == 100
        assert table.created_at == 1000.0
        assert table.updated_at == 2000.0


class TestSchemaImportRequest:
    """Tests for SchemaImportRequest model."""

    def test_empty_request(self):
        """Should create a SchemaImportRequest with all defaults."""
        req = SchemaImportRequest()
        assert req.database_id is None
        assert req.include_tables is None
        assert req.exclude_tables is None

    def test_with_database_id(self):
        """Should create a SchemaImportRequest with a database_id."""
        req = SchemaImportRequest(database_id="db-1")
        assert req.database_id == "db-1"

    def test_with_table_filters(self):
        """Should create a SchemaImportRequest with table filters."""
        req = SchemaImportRequest(
            database_id="db-1",
            include_tables=["users"],
            exclude_tables=["logs"],
        )
        assert req.include_tables == ["users"]
        assert req.exclude_tables == ["logs"]


class TestDescriptionGenerateRequest:
    """Tests for DescriptionGenerateRequest model."""

    def test_empty_request(self):
        """Should create a DescriptionGenerateRequest with all defaults."""
        req = DescriptionGenerateRequest()
        assert req.table_ids is None
        assert req.language == "zh"
        assert req.force is False

    def test_with_table_ids(self):
        """Should create a DescriptionGenerateRequest with table_ids."""
        req = DescriptionGenerateRequest(table_ids=["tbl-1", "tbl-2"])
        assert req.table_ids == ["tbl-1", "tbl-2"]
        assert req.language == "zh"

    def test_with_language_and_force(self):
        """Should create a DescriptionGenerateRequest with language and force."""
        req = DescriptionGenerateRequest(
            table_ids=["tbl-1"],
            language="en",
            force=True,
        )
        assert req.language == "en"
        assert req.force is True


class TestDescriptionUpdateRequest:
    """Tests for DescriptionUpdateRequest model."""

    def test_empty_request(self):
        """Should create a DescriptionUpdateRequest with all defaults."""
        req = DescriptionUpdateRequest()
        assert req.table_id is None
        assert req.column_id is None
        assert req.description == ""
        assert req.description_en == ""

    def test_table_description(self):
        """Should create a DescriptionUpdateRequest for a table description."""
        req = DescriptionUpdateRequest(
            table_id="tbl-1",
            description="用户表",
            description_en="Users table",
        )
        assert req.table_id == "tbl-1"
        assert req.column_id is None
        assert req.description == "用户表"
        assert req.description_en == "Users table"

    def test_column_description(self):
        """Should create a DescriptionUpdateRequest for a column description."""
        req = DescriptionUpdateRequest(
            table_id="tbl-1",
            column_id="col-1",
            description="用户ID",
            description_en="User ID",
        )
        assert req.table_id == "tbl-1"
        assert req.column_id == "col-1"


class TestSchemaStatusResponse:
    """Tests for SchemaStatusResponse model."""

    def test_default_values(self):
        """Should create a SchemaStatusResponse with all default values."""
        resp = SchemaStatusResponse()
        assert resp.schema_status == "pending"
        assert resp.tables_count == 0
        assert resp.columns_count == 0
        assert resp.described_tables == 0
        assert resp.described_columns == 0

    def test_with_values(self):
        """Should create a SchemaStatusResponse with specific values."""
        resp = SchemaStatusResponse(
            schema_status="completed",
            tables_count=10,
            columns_count=50,
            described_tables=5,
            described_columns=25,
        )
        assert resp.schema_status == "completed"
        assert resp.tables_count == 10
        assert resp.columns_count == 50
        assert resp.described_tables == 5
        assert resp.described_columns == 25

    def test_status_accepts_any_string(self):
        """Should accept any string value for schema_status."""
        resp = SchemaStatusResponse(schema_status="in_progress")
        assert resp.schema_status == "in_progress"
