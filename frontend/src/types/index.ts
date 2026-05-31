// ===== 消息 =====
let _msgId = 0
export function nextMsgId(): string {
  return `msg_${++_msgId}_${Date.now()}`
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
  connection_string?: string
  include_tables?: string[]
  exclude_tables?: string[]
  is_active?: boolean
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
