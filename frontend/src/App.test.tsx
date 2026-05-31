import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from './App'
import { useSessionStore } from './store/sessionStore'
import { useConfigStore } from './store/configStore'
import { useUIStore } from './store/uiStore'

const renderApp = async (initialEntries = ['/']) => {
  let result: ReturnType<typeof render> | undefined
  await act(async () => {
    result = render(<MemoryRouter initialEntries={initialEntries}><App /></MemoryRouter>)
  })
  await act(async () => {})
  return result!
}

const mockApi = vi.hoisted(() => ({
  getSessions: vi.fn(),
  getSchema: vi.fn(),
  getDatabases: vi.fn(),
  getConfig: vi.fn(),
  testLLM: vi.fn(),
  sendMessage: vi.fn(),
  getSessionMessages: vi.fn(),
  renameSession: vi.fn(),
  deleteSession: vi.fn(),
  updateConfig: vi.fn(),
  connectDatabase: vi.fn(),
  disconnectDatabase: vi.fn(),
  testConnection: vi.fn(),
  getDatabaseTables: vi.fn(),
  updateDatabase: vi.fn(),
  getMe: vi.fn(),
}))

vi.mock('./api', () => ({ api: mockApi }))

const mockAuthState = {
  user: { id: '1', username: 'admin', role: 'admin' as const, is_active: true },
  token: 'test-token',
  isLoading: false,
  isInitialized: true,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  checkAuth: vi.fn(),
}

vi.mock('./store/authStore', () => ({
  useAuthStore: Object.assign(
    vi.fn((selector?: any) => selector ? selector(mockAuthState) : mockAuthState),
    { getState: vi.fn(() => mockAuthState) }
  ),
}))

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    
    act(() => {
      useSessionStore.setState({ sessions: [], messages: [], activeSessionId: null, isLoading: false })
      useConfigStore.setState({ 
        databases: [], 
        activeDbId: null, 
        schema: [], 
        mode: 'fast',
        llmConnected: null,
        llmConfig: { provider: 'openai', model: 'gpt-4o', name: 'GPT-4o', api_key: '', api_base: '', timeout: 60 },
        safetyConfig: { read_only: true, require_approval: true, max_rows: 1000 }
      })
      useUIStore.setState({ leftOpen: true, error: null })
    })

    mockApi.getSessions.mockResolvedValue({ sessions: [] })
    mockApi.getSchema.mockResolvedValue({ tables: [] })
    mockApi.getDatabases.mockResolvedValue({ databases: [] })
    mockApi.getConfig.mockResolvedValue({ 
      llm: { model: 'gpt-4o', name: 'GPT-4o' },
      safety: { read_only: true, require_approval: true, max_rows: 1000 }
    })
    mockApi.testLLM.mockResolvedValue({ ok: true, message: 'connected' })
  })

  it('renders the app title', async () => {
    await renderApp()
    const titles = screen.getAllByText('数语')
    expect(titles.length).toBeGreaterThanOrEqual(1)
  })

  it('renders status bar', async () => {
    await renderApp()
    expect(screen.getByText(/未连接|未选择/i)).toBeInTheDocument()
  })

  it('calls initialization APIs on mount', async () => {
    await renderApp()
    await waitFor(() => {
      expect(mockApi.getSchema).toHaveBeenCalled()
      expect(mockApi.getDatabases).toHaveBeenCalled()
      expect(mockApi.getConfig).toHaveBeenCalled()
      expect(mockApi.testLLM).toHaveBeenCalled()
    })
  })

  it('shows admin badge for admin users', async () => {
    await renderApp()
    expect(screen.getByText('管理员')).toBeInTheDocument()
  })

  it('shows username in header', async () => {
    await renderApp()
    expect(screen.getByText('admin')).toBeInTheDocument()
  })

  it('renders the index page at root path', async () => {
    await renderApp()
    const taglines = screen.getAllByText('问你的数据')
    expect(taglines.length).toBeGreaterThanOrEqual(1)
    const names = screen.getAllByText('数语')
    expect(names.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('系统管理')).toBeInTheDocument()
  })
})
