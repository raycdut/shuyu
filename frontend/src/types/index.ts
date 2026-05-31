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
  preview_text?: string
  error?: string
}

// ===== 配置 =====
export interface LLMConfig {
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
