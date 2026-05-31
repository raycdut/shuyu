import { describe, it, expect, beforeEach } from 'vitest'
import { useConfigStore } from './configStore'
import type { DatabaseInfo, SchemaTable, LLMConfig, SafetyConfig } from '../types'

describe('configStore', () => {
  beforeEach(() => {
    useConfigStore.setState({
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
    })
  })

  it('starts with default state', () => {
    const state = useConfigStore.getState()
    expect(state.databases).toEqual([])
    expect(state.activeDbId).toBeNull()
    expect(state.mode).toBe('fast')
    expect(state.schema).toEqual([])
    expect(state.llmConnected).toBeNull()
    expect(state.llmConfig.provider).toBe('openai')
    expect(state.llmConfig.model).toBe('gpt-4o')
    expect(state.safetyConfig.read_only).toBe(true)
    expect(state.safetyConfig.max_rows).toBe(1000)
  })

  it('sets databases list', () => {
    const dbs: DatabaseInfo[] = [
      { id: 'db1', name: '测试库', type: 'sqlite', path: '/tmp/test.db' },
    ]
    useConfigStore.getState().setDatabases(dbs)
    expect(useConfigStore.getState().databases).toEqual(dbs)
  })

  it('sets active database id', () => {
    useConfigStore.getState().setActiveDbId('db1')
    expect(useConfigStore.getState().activeDbId).toBe('db1')
  })

  it('sets mode', () => {
    useConfigStore.getState().setMode('normal')
    expect(useConfigStore.getState().mode).toBe('normal')
  })

  it('sets schema', () => {
    const schema: SchemaTable[] = [
      {
        name: 'users',
        columns: [{ name: 'id', type: 'INTEGER' }],
      },
    ]
    useConfigStore.getState().setSchema(schema)
    expect(useConfigStore.getState().schema).toEqual(schema)
  })

  it('sets LLM connected state', () => {
    useConfigStore.getState().setLlmConnected(false)
    expect(useConfigStore.getState().llmConnected).toBe(false)

    useConfigStore.getState().setLlmConnected(true)
    expect(useConfigStore.getState().llmConnected).toBe(true)
  })

  it('sets LLM config directly', () => {
    const cfg: LLMConfig = {
      provider: 'anthropic',
      model: 'claude-3-opus',
      api_key: 'sk-test',
      api_base: '',
      timeout: 120,
    }
    useConfigStore.getState().setLLMConfig(cfg)
    expect(useConfigStore.getState().llmConfig.provider).toBe('anthropic')
    expect(useConfigStore.getState().llmConfig.model).toBe('claude-3-opus')
  })

  it('updates LLM config partially via updater function', () => {
    useConfigStore.getState().setLLMConfig((prev) => ({
      ...prev,
      model: 'gpt-4-turbo',
    }))
    expect(useConfigStore.getState().llmConfig.model).toBe('gpt-4-turbo')
    expect(useConfigStore.getState().llmConfig.provider).toBe('openai')
  })

  it('sets safety config directly', () => {
    const cfg: SafetyConfig = {
      read_only: false,
      require_approval: false,
      max_rows: 5000,
    }
    useConfigStore.getState().setSafetyConfig(cfg)
    expect(useConfigStore.getState().safetyConfig.read_only).toBe(false)
    expect(useConfigStore.getState().safetyConfig.max_rows).toBe(5000)
  })

  it('updates safety config partially via updater function', () => {
    useConfigStore.getState().setSafetyConfig((prev) => ({
      ...prev,
      max_rows: 500,
    }))
    expect(useConfigStore.getState().safetyConfig.max_rows).toBe(500)
    expect(useConfigStore.getState().safetyConfig.read_only).toBe(true)
  })
})
