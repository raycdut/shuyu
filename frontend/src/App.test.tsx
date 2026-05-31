import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import App from './App'

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

// Mock auth store to return a logged-in user
vi.mock('./store/authStore', () => ({
  useAuthStore: Object.assign(
    vi.fn((selector?: any) => {
      const state = {
        user: { id: '1', username: 'admin', role: 'admin' as const, is_active: true },
        token: 'test-token',
        isLoading: false,
        isInitialized: true,
        login: vi.fn(),
        register: vi.fn(),
        logout: vi.fn(),
        checkAuth: vi.fn(),
      }
      return selector ? selector(state) : state
    }),
    { getState: vi.fn(() => ({ logout: vi.fn() })) }
  ),
}))

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApi.getSessions.mockResolvedValue({ sessions: [] })
    mockApi.getSchema.mockResolvedValue({ tables: [] })
    mockApi.getDatabases.mockResolvedValue({ databases: [] })
    mockApi.getConfig.mockResolvedValue({})
    mockApi.testLLM.mockResolvedValue({ ok: true, message: 'connected' })
  })

  it('renders the app title', () => {
    render(<App />)
    expect(screen.getByText('Data Chat')).toBeInTheDocument()
  })

  it('renders status bar', () => {
    render(<App />)
    expect(screen.getByText('未连接')).toBeInTheDocument()
  })

  it('calls initialization APIs on mount', () => {
    render(<App />)
    expect(mockApi.getSessions).toHaveBeenCalled()
    expect(mockApi.getSchema).toHaveBeenCalled()
    expect(mockApi.getDatabases).toHaveBeenCalled()
    expect(mockApi.getConfig).toHaveBeenCalled()
    expect(mockApi.testLLM).toHaveBeenCalled()
  })

  it('renders chat input area', () => {
    render(<App />)
    expect(screen.getByPlaceholderText('给 Shuyu 发送消息')).toBeInTheDocument()
  })

  it('shows example questions in empty state', () => {
    render(<App />)
    expect(screen.getByText('有哪些数据表？')).toBeInTheDocument()
    expect(screen.getByText('帮我分析一下数据')).toBeInTheDocument()
  })

  it('sends a message and shows user message', async () => {
    mockApi.sendMessage.mockResolvedValue({
      reply: '这是分析结果',
      session_id: 'new-session-1',
      tool_calls: [],
      sql_queries: [],
    })

    render(<App />)
    const input = screen.getByPlaceholderText('给 Shuyu 发送消息')
    fireEvent.change(input, { target: { value: '帮我查一下数据' } })
    fireEvent.keyDown(input, { key: 'Enter', ctrlKey: true })

    expect(await screen.findByText('帮我查一下数据')).toBeInTheDocument()
    expect(await screen.findByText('这是分析结果')).toBeInTheDocument()
  })

  it('shows error message when sendMessage fails', async () => {
    mockApi.sendMessage.mockRejectedValue(new Error('网络错误'))

    render(<App />)
    const input = screen.getByPlaceholderText('给 Shuyu 发送消息')
    fireEvent.change(input, { target: { value: '查数据' } })
    fireEvent.keyDown(input, { key: 'Enter', ctrlKey: true })

    expect(await screen.findByText(/请求失败/)).toBeInTheDocument()
    expect(screen.getByText(/网络错误/)).toBeInTheDocument()
  })

  it('toggles sidebar visibility', () => {
    render(<App />)
    expect(screen.getByText('暂无历史会话')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('切换侧栏'))
    expect(screen.queryByText('暂无历史会话')).not.toBeInTheDocument()
  })

  it('toggles config panel visibility', () => {
    render(<App />)
    expect(screen.getByText('LLM 提供商')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('切换配置面板'))
    expect(screen.queryByText('LLM 提供商')).not.toBeInTheDocument()
  })

  it('shows error toast when loadSessions fails', async () => {
    mockApi.getSessions.mockRejectedValue(new Error('连接被拒绝'))

    render(<App />)
    expect(await screen.findByText(/加载会话失败/)).toBeInTheDocument()
    expect(screen.getByText(/连接被拒绝/)).toBeInTheDocument()
  })

  it('sends message with Ctrl+Enter', async () => {
    mockApi.sendMessage.mockResolvedValue({
      reply: '结果',
      session_id: 's1',
      tool_calls: [],
      sql_queries: [],
    })

    render(<App />)
    const input = screen.getByPlaceholderText('给 Shuyu 发送消息')

    fireEvent.change(input, { target: { value: 'Ctrl+Enter 发送测试' } })
    fireEvent.keyDown(input, { key: 'Enter', ctrlKey: true })

    expect(await screen.findByText('Ctrl+Enter 发送测试')).toBeInTheDocument()
  })

  it('shows admin badge for admin users', () => {
    render(<App />)
    expect(screen.getByText('管理员')).toBeInTheDocument()
  })

  it('shows username in header', () => {
    render(<App />)
    expect(screen.getByText('admin')).toBeInTheDocument()
  })
})
