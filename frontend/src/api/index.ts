import type {
  ChatResponse,
  SessionListResponse,
  SessionMessagesResponse,
  SchemaResponse,
  DatabaseListResponse,
  DBConnectRequest,
  AppConfig,
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  UserInfo,
  ImportedTable,
  SchemaStatus,
  SystemConfig,
  UserConfig,
  UserAvailableOptions,
  ConfigChangeLogEntry,
} from '../types'

const BASE = '/api'

function getToken(): string | null {
  return localStorage.getItem('auth_token')
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const res = await fetch(`${BASE}${url}`, {
    headers,
    ...options,
  })
  if (res.status === 401) {
    localStorage.removeItem('auth_token')
    window.dispatchEvent(new CustomEvent('auth:unauthorized'))
  }
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status}: ${text || res.statusText}`)
  }
  return res.json()
}

export const api = {
  // ===== 认证 =====
  login(data: LoginRequest): Promise<LoginResponse> {
    return request('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  register(data: RegisterRequest): Promise<UserInfo> {
    return request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  getMe(): Promise<UserInfo> {
    return request('/auth/me')
  },

  // ===== 聊天 =====
  sendMessage(message: string, sessionId?: string, dbId?: string, mode?: string): Promise<ChatResponse> {
    return request('/chat', {
      method: 'POST',
      body: JSON.stringify({ message, session_id: sessionId || null, db_id: dbId || null, mode: mode || 'fast' }),
    })
  },

  // ===== 会话 =====
  getSessions(): Promise<SessionListResponse> {
    return request('/sessions')
  },

  getSessionMessages(sessionId: string): Promise<SessionMessagesResponse> {
    return request(`/sessions/${sessionId}/messages`)
  },

  renameSession(sessionId: string, title: string): Promise<void> {
    return request(`/sessions/${sessionId}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    })
  },

  deleteSession(sessionId: string): Promise<void> {
    return request(`/sessions/${sessionId}`, { method: 'DELETE' })
  },

  // ===== 数据库 Schema =====
  getSchema(): Promise<SchemaResponse> {
    return request('/schema')
  },

  // ===== 数据库管理 =====
  getDatabases(): Promise<DatabaseListResponse> {
    return request('/database')
  },

  connectDatabase(data: DBConnectRequest): Promise<any> {
    return request('/database/connect', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  disconnectDatabase(id: string): Promise<void> {
    return request(`/database/${id}`, { method: 'DELETE' })
  },

  // ===== 配置 =====
  getConfig(): Promise<AppConfig> {
    return request('/config')
  },

  updateConfig(data: Partial<AppConfig>): Promise<void> {
    return request('/config', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  // ===== LLM 测试 =====
  testLLM(config?: { model_id?: string; provider?: string }): Promise<{ ok: boolean; message: string }> {
    return request('/config/llm/test', {
      method: 'POST',
      body: JSON.stringify(config || {}),
    })
  },

  // ===== 数据库连接测试 =====
  testConnection(data: DBConnectRequest): Promise<{ ok: boolean; message: string }> {
    return request('/database/test', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  // ===== 数据库表结构 =====
  getDatabaseTables(dbId: string): Promise<SchemaResponse> {
    return request(`/database/${dbId}/tables`)
  },

  // ===== 更新数据库配置 =====
  updateDatabase(dbId: string, data: { include_tables?: string[]; exclude_tables?: string[] }): Promise<void> {
    return request(`/database/${dbId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  },

  updateDatabaseConnection(dbId: string, data: any): Promise<{ ok: boolean; message: string }> {
    return request(`/database/${dbId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  },

  // ===== 管理员：用户管理 =====
  getUsers(): Promise<UserInfo[]> {
    return request('/admin/users')
  },

  updateUser(userId: string, data: { role?: string; is_active?: boolean }): Promise<UserInfo> {
    return request(`/admin/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  },

  deleteUser(userId: string): Promise<void> {
    return request(`/admin/users/${userId}`, { method: 'DELETE' })
  },

  getUserDatabases(userId: string): Promise<{ database_ids: string[] }> {
    return request(`/admin/users/${userId}/databases`)
  },

  setUserDatabases(userId: string, databaseIds: string[]): Promise<{ database_ids: string[] }> {
    return request(`/admin/users/${userId}/databases`, {
      method: 'PUT',
      body: JSON.stringify({ database_ids: databaseIds }),
    })
  },

  // ===== Schema 管理 =====
  importSchema(dbId: string, data?: { include_tables?: string[]; exclude_tables?: string[] }): Promise<{ ok: boolean; tables_count: number; columns_count: number; message: string }> {
    return request(`/database/${dbId}/schema/import`, {
      method: 'POST',
      body: JSON.stringify(data || {}),
    })
  },

  getImportedSchema(dbId: string): Promise<{ tables: ImportedTable[] }> {
    return request(`/database/${dbId}/schema`)
  },

  getSchemaStatus(dbId: string): Promise<SchemaStatus> {
    return request(`/database/${dbId}/schema/status`)
  },

  generateDescriptions(dbId: string, data?: { table_ids?: string[]; language?: string; force?: boolean }): Promise<{ ok: boolean; tables_described: number; columns_described: number; message: string }> {
    return request(`/database/${dbId}/schema/describe`, {
      method: 'POST',
      body: JSON.stringify(data || {}),
    })
  },

  updateDescription(dbId: string, data: { table_id?: string; column_id?: string; description: string; description_en?: string }): Promise<{ ok: boolean; message: string }> {
    return request(`/database/${dbId}/schema/describe`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  },

  // ===== 管理员：系统配置 =====
  getSystemConfig(): Promise<SystemConfig> {
    return request('/admin/config')
  },

  updateSystemConfig(config: Partial<SystemConfig>): Promise<SystemConfig> {
    return request('/admin/config', {
      method: 'PATCH',
      body: JSON.stringify(config),
    })
  },

  getConfigChangelog(): Promise<ConfigChangeLogEntry[]> {
    return request('/admin/config/changelog')
  },

  // ===== 用户：个人配置 =====
  getUserConfig(): Promise<UserConfig> {
    return request('/user/config')
  },

  updateUserConfig(config: Partial<Record<string, any>>): Promise<{ merged: UserConfig; overrides: Partial<UserConfig> }> {
    return request('/user/config', {
      method: 'PUT',
      body: JSON.stringify(config),
    })
  },

  getUserAvailableOptions(): Promise<UserAvailableOptions> {
    return request('/user/config/available')
  },

  // ===== Prompt 管理 =====
  getPrompts(category?: string): Promise<import('../types').PromptListResponse> {
    const params = category ? `?category=${encodeURIComponent(category)}` : ''
    return request(`/prompts${params}`)
  },

  getPrompt(id: number): Promise<import('../types').PromptInfo> {
    return request(`/prompts/${id}`)
  },

  upsertPrompt(category: string, content: string): Promise<import('../types').UpsertPromptResponse> {
    return request('/prompts', {
      method: 'PUT',
      body: JSON.stringify({ category, content }),
    })
  },

  activatePrompt(id: number): Promise<import('../types').ActivatePromptResponse> {
    return request(`/prompts/${id}/activate`, { method: 'PATCH' })
  },

  getActivePrompts(): Promise<import('../types').ActivePromptsResponse> {
    return request('/prompts/active')
  },

  getDefaultPrompt(category: string): Promise<import('../types').DefaultPromptResponse> {
    return request(`/prompts/${encodeURIComponent(category)}/default`)
  },

  // ===== Admin Stats =====
  getAdminStats(days?: number): Promise<import('../types').AdminStatsResponse> {
    const params = days ? `?days=${days}` : ''
    return request(`/admin/stats${params}`)
  },
}
