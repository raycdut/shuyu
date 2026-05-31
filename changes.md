# Change Log

## 2026-05-31

### Added tests for backend Python source files

Created two comprehensive test files under `backend/tests/`:

#### `tests/test_models.py`
- **TestChatRequest** (6 tests): creation with various params, defaults, empty message, custom mode
- **TestChatResponse** (7 tests): minimal/all fields, default empty lists, missing required fields
- **TestSessionRenameRequest** (3 tests): creation with title, empty title, missing title
- **TestSessionMessagesResponse** (4 tests): creation with messages, empty messages, missing fields
- **TestConfigUpdate** (5 tests): empty/llm-only/safety-only/both updates, nested dicts
- **TestLLMTestResult** (5 tests): success/failure results, empty message, missing fields
- **TestDBConnectRequest** (5 tests): minimal, MySQL connection, file path, connection string, table filters
- **TestDBInfo** (3 tests): minimal, all fields, missing id
- **TestDBTestResult** (3 tests): ok/fail results, missing ok field
- **TestColumnSchema** (3 tests): minimal, all fields, primary key
- **TestTableSchema** (3 tests): minimal, view type, multiple columns
- **TestImportedColumnInfo** (3 tests): minimal, with sample values, empty sample values
- **TestImportedTableInfo** (2 tests): minimal, with nested columns
- **TestSchemaImportRequest** (3 tests): empty, with database_id, with table filters
- **TestDescriptionGenerateRequest** (3 tests): empty, with table_ids, with language and force
- **TestDescriptionUpdateRequest** (3 tests): empty, table description, column description
- **TestSchemaStatusResponse** (3 tests): default values, with values, custom status

#### `tests/test_auth_middleware.py`
- **TestGetCurrentUser** (10 tests): missing/empty/non-bearer auth header, invalid token, user not found, disabled user, valid user/admin, verifies correct arguments passed to mocked functions
- **TestRequireAdmin** (4 tests): admin passes, non-admin raises 403, custom role case, disabled admin

#### Test results
- All 78 tests passed successfully
- Follows existing patterns: pytest classes, SQLite `:memory:` fixtures (where applicable), `from app.xxx import yyy` style, function-level docstrings
