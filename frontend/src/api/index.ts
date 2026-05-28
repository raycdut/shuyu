import type {
  ChatResponse,
  SessionListResponse,
  SessionMessagesResponse,
  SchemaResponse,
  DatabaseListResponse,
  DBConnectRequest,
  AppConfig,
} from '../types'

const BASE = '/api'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status}: ${text || res.statusText}`)
  }
  return res.json()
}

export const api = {
  // ===== 聊天 =====
  sendMessage(message: string, sessionId?: string, dbId?: string): Promise<ChatResponse> {
    return request('/chat', {
      method: 'POST',
      body: JSON.stringify({ message, session_id: sessionId || null, db_id: dbId || null }),
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
  testLLM(config?: { api_key?: string; api_base?: string; model?: string }): Promise<{ ok: boolean; message: string }> {
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
}
