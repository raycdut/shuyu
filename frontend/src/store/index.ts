import { create } from 'zustand'
import { Session, DatabaseInfo, LLMConfig, SafetyConfig, Message, SchemaTable } from '../types'

/**
 * 全局状态存储接口
 */
interface AppState {
  // 会话状态
  sessions: Session[]
  activeSessionId: string | null
  messages: Message[]
  isLoading: boolean
  
  // 数据库状态
  databases: DatabaseInfo[]
  activeDbId: string | null
  mode: string
  schema: SchemaTable[]
  
  // 配置状态
  llmConnected: boolean | null
  llmConfig: LLMConfig
  safetyConfig: SafetyConfig
  
  // UI 状态
  leftOpen: boolean
  rightOpen: boolean
  showDashboard: boolean
  error: string | null
  
  // 看板状态
  dashboardItems: DashboardItem[]
  
  // Actions
  setSessions: (sessions: Session[]) => void
  setActiveSessionId: (id: string | null) => void
  setMessages: (messages: Message[] | ((prev: Message[]) => Message[])) => void
  setIsLoading: (loading: boolean) => void
  
  setDatabases: (databases: DatabaseInfo[]) => void
  setActiveDbId: (id: string | null) => void
  setMode: (mode: string) => void
  setSchema: (schema: SchemaTable[]) => void
  
  setLlmConnected: (connected: boolean | null) => void
  setLLMConfig: (config: LLMConfig | ((prev: LLMConfig) => LLMConfig)) => void
  setSafetyConfig: (config: SafetyConfig | ((prev: SafetyConfig) => SafetyConfig)) => void
  
  setLeftOpen: (open: boolean) => void
  setRightOpen: (open: boolean) => void
  setShowDashboard: (show: boolean) => void
  setError: (error: string | null) => void
  
  addDashboardItem: (item: DashboardItem) => void
  removeDashboardItem: (id: string) => void
}

/**
 * 看板条目接口
 */
export interface DashboardItem {
  id: string
  title: string
  columns: string[]
  data: any[][]
  type: 'line' | 'bar' | 'table'
  createdAt: number
}

/**
 * 创建 Zustand Store
 */
export const useStore = create<AppState>((set) => ({
  // 初始状态
  sessions: [],
  activeSessionId: null,
  messages: [],
  isLoading: false,
  
  databases: [],
  activeDbId: null,
  mode: 'fast',
  schema: [],
  
  llmConnected: null,
  llmConfig: {
    provider: 'openai',
    model: 'gpt-4o',
    name: 'OpenAI (Default)',
    api_key: '',
    api_base: '',
    timeout: 60,
  },
  safetyConfig: {
    read_only: true,
    require_approval: true,
    max_rows: 1000,
  },
  
  leftOpen: true,
  rightOpen: true,
  showDashboard: false,
  error: null,
  
  dashboardItems: [],
  
  // Actions 实现
  setSessions: (sessions) => set({ sessions }),
  setActiveSessionId: (activeSessionId) => set({ activeSessionId }),
  setMessages: (messages) => set((state) => ({ 
    messages: typeof messages === 'function' ? messages(state.messages) : messages 
  })),
  setIsLoading: (isLoading) => set({ isLoading }),
  
  setDatabases: (databases) => set({ databases }),
  setActiveDbId: (activeDbId) => set({ activeDbId }),
  setMode: (mode) => set({ mode }),
  setSchema: (schema) => set({ schema }),
  
  setLlmConnected: (llmConnected) => set({ llmConnected }),
  setLLMConfig: (config) => set((state) => ({
    llmConfig: typeof config === 'function' ? config(state.llmConfig) : config
  })),
  setSafetyConfig: (config) => set((state) => ({
    safetyConfig: typeof config === 'function' ? config(state.safetyConfig) : config
  })),
  
  setLeftOpen: (leftOpen) => set({ leftOpen }),
  setRightOpen: (rightOpen) => set({ rightOpen }),
  setShowDashboard: (showDashboard) => set({ showDashboard }),
  setError: (error) => set({ error }),
  
  addDashboardItem: (item) => set((state) => ({
    dashboardItems: [item, ...state.dashboardItems]
  })),
  removeDashboardItem: (id) => set((state) => ({
    dashboardItems: state.dashboardItems.filter(i => i.id !== id)
  })),
}))
