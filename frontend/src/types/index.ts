// ===== 消息 =====
let _msgCounter = 0
export function nextMsgId(): string {
  return `msg_${++_msgCounter}_${crypto.randomUUID().slice(0, 8)}`
}

export interface ProgressStep {
  label: string
  status: 'pending' | 'running' | 'done' | 'error'
  detail?: string
}

export interface Message {
  id?: string
  role: 'user' | 'assistant' | 'system'
  content: string
  tool_calls?: ToolCall[]
  sql_queries?: string[]
  query_results?: QueryResultInfo[]
  isPlan?: boolean
  planContent?: string
  isProgress?: boolean
  progressSteps?: ProgressStep[]
  progressTitle?: string
}

export interface ToolCall {
  id: string
  type: string
  function: {
    name: string
    arguments: string
  }
}

// ===== 会话 =====
export interface Session {
  id: string
  title: string
  messages: number
  created_at?: string
  last_active?: number
}

export interface SessionListResponse {
  sessions: Session[]
}

export interface SessionMessagesResponse {
  messages: Message[]
  session_id: string
}

// ===== 数据库 =====
export interface DatabaseInfo {
  id: string
  name: string
  type: string
  path?: string
  connection_string?: string
  host?: string
  port?: number
  user?: string
  password?: string
  database?: string
  include_tables?: string[]
  exclude_tables?: string[]
  is_active?: boolean
  schema_status?: string
}

export interface DatabaseListResponse {
  databases: DatabaseInfo[]
}

export interface SchemaTable {
  name: string
  type?: string
  columns: { name: string; type: string }[]
}

export interface SchemaResponse {
  tables: SchemaTable[]
}

export interface DBConnectRequest {
  name: string
  type: string
  path?: string
  connection_string?: string
  host?: string
  port?: number
  user?: string
  password?: string
  database?: string
  include_tables?: string[]
  exclude_tables?: string[]
}

// ===== 聊天的请求/响应 =====
export interface ChatRequest {
  message: string
  session_id?: string
  db_id?: string
  mode?: string
}

export interface ChatResponse {
  reply: string
  session_id: string
  tool_calls: ToolCall[]
  sql_queries: string[]
  query_results: QueryResultInfo[]
}

export interface QueryResultInfo {
  qn: number
  question?: string
  sql: string
  ok: boolean
  row_count?: number
  columns?: string[]
  data?: any[][]
  preview_text?: string
  error?: string
}

// ===== 配置 =====
export interface LLMConfig {
  id?: string
  name?: string
  provider: string
  model: string
  api_key: string
  api_base: string
  timeout: number
}

export interface SafetyConfig {
  read_only: boolean
  require_approval: boolean
  max_rows: number
}

export interface AppConfig {
  llm?: Partial<LLMConfig>
  safety?: Partial<SafetyConfig>
  database?: any
}

// ===== 认证 =====
export interface UserInfo {
  id: string
  username: string
  role: 'admin' | 'user'
  is_active: boolean
  created_at?: string
  last_login_at?: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: UserInfo
}

export interface RegisterRequest {
  username: string
  password: string
}

// ===== Schema 管理 =====
export interface ImportedTable {
  id: string
  database_id: string
  table_name: string
  table_type: string
  description: string
  description_en: string
  row_count?: number
  columns: ImportedColumn[]
  created_at: number
  updated_at: number
}

export interface ImportedColumn {
  id: string
  column_name: string
  data_type: string
  is_nullable: boolean
  is_primary_key: boolean
  description: string
  description_en: string
  sample_values?: string[]
}

export interface SchemaStatus {
  schema_status: 'pending' | 'importing' | 'imported' | 'error'
  tables_count: number
  columns_count: number
  described_tables: number
  described_columns: number
}

// ===== 配置管理 =====
export interface LLMModelInstance {
  id: string
  name: string
  provider: string
  model: string
  api_key?: string
  api_base?: string
  timeout?: number
  enabled: boolean
  is_system_default: boolean
  is_connected?: boolean | null
}

export interface SystemConfig {
  llm: {
    models: LLMModelInstance[]
  }
  safety: {
    read_only: boolean
    require_approval: boolean
    max_rows: number
    blocked_tables: string[]
    masked_columns: string[]
  }
  advanced: {
    session_expire_minutes: number
    max_sessions_per_user: number
    allow_user_llm_config: boolean
    allow_user_safety_override: boolean
    llm_temperature_range: { min: number; max: number; default: number }
  }
  storage: {
    log_interval: string
    log_retention_days: number
  }
}

export interface UserPreferences {
  language: string
  temperature: number
  theme: string
  default_view: string
}

export interface UserConfig {
  llm: {
    provider: string
    model: string
    api_key: string
    api_base: string
    timeout: number
  }
  safety: {
    read_only: boolean
    require_approval: boolean
    max_rows: number
  }
  preferences: UserPreferences
}

export interface UserAvailableOptions {
  llm: {
    providers: { provider: string; label: string; models: string[] }[]
    models: { id: string; name: string; provider: string; model: string }[]
    can_use_custom_api_key: boolean
    can_use_custom_api_base: boolean
  }
  safety: {
    read_only: { editable: boolean; value: boolean }
    require_approval: { editable: boolean; value: boolean }
    max_rows: { editable: boolean; min: number; max: number; default: number }
  }
  preferences: {
    language: { options: string[] }
    temperature: { min: number; max: number; step: number }
  }
}

export interface ConfigChangeLogEntry {
  id: number
  config_type: string
  user_id: string | null
  changed_by: string
  summary: string
  diff: string | null
  created_at: string
}

// ===== Prompt 管理 =====
export interface PromptInfo {
  id: number
  name: string
  content: string
  version: number
  is_active: boolean
  created_at: number
}

export interface PromptListItem {
  id: number
  name: string
  version: number
  is_active: boolean
  created_at: number
}

export interface PromptListResponse {
  prompts: PromptListItem[]
}

export interface ActivePromptEntry {
  id: number | null
  content: string
  version: number | null
}

export interface ActivePromptsResponse {
  [category: string]: ActivePromptEntry
}

export interface UpsertPromptResponse {
  ok: boolean
  version: number
  error?: string
}

export interface ActivatePromptResponse {
  ok: boolean
  error?: string
}

export interface DefaultPromptResponse {
  category: string
  content: string
  error?: string
}

// ===== Admin Stats =====
export interface OverviewStats {
  total_users: number
  total_sessions: number
  total_messages: number
  today_logins: number
  today_questions: number
  today_token_prompt: number
  today_token_completion: number
  today_token_total: number
}

export interface TrendPoint {
  date: string
  value: number
}

export interface TrendsData {
  active_users: TrendPoint[]
  questions: TrendPoint[]
  token_usage: TrendPoint[]
}

export interface TopUser {
  username: string
  question_count: number
  last_active: string
}

export interface ModelUsage {
  model: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  call_count: number
}

export interface AdminStatsResponse {
  overview: OverviewStats
  trends: TrendsData
  top_users: TopUser[]
  model_usage: ModelUsage[]
}
