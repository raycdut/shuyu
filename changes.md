# Change Log

## 2026-05-31

### Limited maximum LLM temperature to 0.5 for objective data analysis

**Motivation**: The system's data insights should be absolutely objective. Low temperature (low "warmth") ensures more deterministic, factual outputs rather than creative ones.

**Changes**:

1. **Default max temperature reduced** (`backend/app/admin_config/service.py`):
   - `llm_temperature_range.max`: 1.0 → 0.5 (both `DEFAULT_SYSTEM_CONFIG` and fallback in `get_user_available_options`)

2. **Backend enforcement** (`backend/app/admin_config/service.py`):
   - `update_user_config()`: When saving user preferences, clamps `temperature` to the configured `llm_temperature_range.max`
   - `_merge_configs()`: When merging user preferences into runtime config, clamps temperature to the configured max

3. **Frontend slider limit** (`frontend/src/components/ConfigPanel.tsx`):
   - Temperature slider now reads `tempMax` from `api.getUserAvailableOptions().preferences.temperature.max`
   - Slider `max` changes from hardcoded `"1"` to dynamic `{tempMax}`
   - When the panel opens, temperature is clamped to max

4. **Fixed pre-existing TS error** (`frontend/src/pages/AdminSettings/tabs/AdvancedSettingsTab.tsx`):
   - Added missing `llm_temperature_range` property when saving advanced settings

**Verification**: All 120 frontend tests and 234 backend tests pass.

**Root cause**: Frontend API client had duplicate `/api` prefix in prompt-related API calls. The `request()` function already prepends `BASE = '/api'` to all URLs, but the prompt API paths were hardcoded with `/api/prompts/...`, resulting in double-prefixed URLs (`/api/api/prompts/...`).

**Fix**: Removed the redundant `/api` prefix from all 6 prompt API call paths in `frontend/src/api/index.ts`:
- `getPrompts`: `/api/prompts` → `/prompts`
- `getPrompt`: `/api/prompts/{id}` → `/prompts/{id}`
- `upsertPrompt`: `/api/prompts` → `/prompts`
- `activatePrompt`: `/api/prompts/{id}/activate` → `/prompts/{id}/activate`
- `getActivePrompts`: `/api/prompts/active` → `/prompts/active`
- `getDefaultPrompt`: `/api/prompts/{category}/default` → `/prompts/{category}/default`

**Verification**: All 120 frontend tests and 234 backend tests pass. TypeScript compilation produces no errors.

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
