import { create } from 'zustand'
import { DatabaseInfo, LLMConfig, SafetyConfig, SchemaTable } from '../types'

/**
 * 配置管理状态接口
 */
interface ConfigState {
  /** 数据库列表 */
  databases: DatabaseInfo[]
  /** 当前激活的数据库 ID */
  activeDbId: string | null
  /** 当前模式（fast / normal） */
  mode: string
  /** 数据库 schema 信息 */
  schema: SchemaTable[]

  /** LLM 连接状态 */
  llmConnected: boolean | null
  /** LLM 配置 */
  llmConfig: LLMConfig
  /** 安全配置 */
  safetyConfig: SafetyConfig

  /** 设置数据库列表 */
  setDatabases: (databases: DatabaseInfo[]) => void
  /** 设置当前激活的数据库 ID */
  setActiveDbId: (id: string | null) => void
  /** 设置模式 */
  setMode: (mode: string) => void
  /** 设置 schema 信息 */
  setSchema: (schema: SchemaTable[]) => void

  /** 设置 LLM 连接状态 */
  setLlmConnected: (connected: boolean | null) => void
  /**
   * 设置 LLM 配置
   * 支持直接传入配置对象或通过函数基于前一次值更新
   */
  setLLMConfig: (config: LLMConfig | ((prev: LLMConfig) => LLMConfig)) => void
  /**
   * 设置安全配置
   * 支持直接传入配置对象或通过函数基于前一次值更新
   */
  setSafetyConfig: (config: SafetyConfig | ((prev: SafetyConfig) => SafetyConfig)) => void
}

/**
 * LLM 配置默认值
 */
const DEFAULT_LLM_CONFIG: LLMConfig = {
  provider: 'openai',
  model: 'gpt-4o',
  name: 'OpenAI (Default)',
  api_key: '',
  api_base: '',
  timeout: 60,
}

/**
 * 安全配置默认值
 */
const DEFAULT_SAFETY_CONFIG: SafetyConfig = {
  read_only: true,
  require_approval: true,
  max_rows: 1000,
}

/**
 * 配置管理 Zustand Store
 * 管理数据库配置、LLM 配置和安全配置
 */
export const useConfigStore = create<ConfigState>((set) => ({
  databases: [],
  activeDbId: null,
  mode: 'fast',
  schema: [],

  llmConnected: null,
  llmConfig: { ...DEFAULT_LLM_CONFIG },
  safetyConfig: { ...DEFAULT_SAFETY_CONFIG },

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
}))
