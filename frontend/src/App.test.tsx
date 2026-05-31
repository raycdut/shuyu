import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from './App'
import { useSessionStore } from './store/sessionStore'
import { useConfigStore } from './store/configStore'
import { useUIStore } from './store/uiStore'

const renderApp = () => render(<MemoryRouter><App /></MemoryRouter>)

// Mock the api module
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

// Mock auth store with stable state to avoid infinite loops in useEffect
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
    
    // Reset real stores to initial state
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

  it('renders the app title', () => {
    renderApp()
    expect(screen.getByText('Data Chat')).toBeInTheDocument()
  })

  it('renders status bar', () => {
    renderApp()
    expect(screen.getByText(/未连接|未选择/i)).toBeInTheDocument()
  })

  it('calls initialization APIs on mount', () => {
    renderApp()
    expect(mockApi.getSessions).toHaveBeenCalled()
    expect(mockApi.getSchema).toHaveBeenCalled()
    expect(mockApi.getDatabases).toHaveBeenCalled()
    expect(mockApi.getConfig).toHaveBeenCalled()
    expect(mockApi.testLLM).toHaveBeenCalled()
  })

  it('renders chat input area', () => {
    renderApp()
    expect(screen.getByPlaceholderText(/发送消息/)).toBeInTheDocument()
  })

  it('shows example questions in empty state', () => {
    renderApp()
    expect(screen.getByText('有哪些数据表？')).toBeInTheDocument()
  })

  it('sends a message and shows user message', async () => {
    mockApi.sendMessage.mockResolvedValue({
      reply: '这是分析结果',
      session_id: 'new-session-1',
      tool_calls: [],
      sql_queries: [],
    })

    // Setup state for the test
    act(() => {
      useConfigStore.setState({ activeDbId: 'db1' })
    })

    renderApp()

    const input = screen.getByPlaceholderText(/发送消息/)
    
    await act(async () => {
      fireEvent.change(input, { target: { value: '帮我查一下数据' } })
      fireEvent.keyDown(input, { key: 'Enter', ctrlKey: true })
    })

    // Wait for messages to appear in the UI
    await waitFor(() => {
      expect(screen.getByText('帮我查一下数据')).toBeInTheDocument()
    }, { timeout: 10000 })

    await waitFor(() => {
      expect(screen.getByText('这是分析结果')).toBeInTheDocument()
    }, { timeout: 10000 })
  }, 15000)

  it('shows error message when sendMessage fails', async () => {
    mockApi.sendMessage.mockRejectedValue(new Error('网络错误'))

    act(() => {
      useConfigStore.setState({ activeDbId: 'db1' })
    })

    renderApp()

    const input = screen.getByPlaceholderText(/发送消息/)
    
    await act(async () => {
      fireEvent.change(input, { target: { value: '查数据' } })
      fireEvent.keyDown(input, { key: 'Enter', ctrlKey: true })
    })

    await waitFor(() => {
      expect(screen.getByText(/请求失败/)).toBeInTheDocument()
      expect(screen.getByText(/网络错误/)).toBeInTheDocument()
    }, { timeout: 10000 })
  }, 15000)

  it('toggles sidebar visibility', async () => {
    renderApp()
    
    // Initial state: sidebar is open
    expect(screen.getByText('历史会话')).toBeInTheDocument()
    
    // Toggle to close
    await act(async () => {
      fireEvent.click(screen.getByLabelText('切换侧栏'))
    })
    
    // Wait for it to disappear
    await waitFor(() => {
      expect(screen.queryByText('历史会话')).not.toBeInTheDocument()
    }, { timeout: 10000 })

    // Toggle back to open
    await act(async () => {
      fireEvent.click(screen.getByLabelText('切换侧栏'))
    })

    await waitFor(() => {
      expect(screen.getByText('历史会话')).toBeInTheDocument()
    }, { timeout: 10000 })
  }, 15000)

  it('shows admin badge for admin users', () => {
    renderApp()
    expect(screen.getByText('管理员')).toBeInTheDocument()
  })

  it('shows username in header', () => {
    renderApp()
    expect(screen.getByText('admin')).toBeInTheDocument()
  })
})
