import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from './App'
import type { AppConfig } from './types'

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
}))

vi.mock('./api', () => ({ api: mockApi }))

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Default successful responses
    mockApi.getSessions.mockResolvedValue({ sessions: [] })
    mockApi.getSchema.mockResolvedValue({ tables: [] })
    mockApi.getDatabases.mockResolvedValue({ databases: [] })
    mockApi.getConfig.mockResolvedValue({} as AppConfig)
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
    expect(screen.getByPlaceholderText('输入你的问题…')).toBeInTheDocument()
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
    const input = screen.getByPlaceholderText('输入你的问题…')
    const sendBtn = screen.getByText('发送')

    fireEvent.change(input, { target: { value: '帮我查一下数据' } })
    fireEvent.click(sendBtn)

    // User message should appear
    expect(await screen.findByText('帮我查一下数据')).toBeInTheDocument()
    // Assistant reply should appear
    expect(await screen.findByText('这是分析结果')).toBeInTheDocument()
  })

  it('shows error message when sendMessage fails', async () => {
    mockApi.sendMessage.mockRejectedValue(new Error('网络错误'))

    render(<App />)
    const input = screen.getByPlaceholderText('输入你的问题…')
    const sendBtn = screen.getByText('发送')

    fireEvent.change(input, { target: { value: '查数据' } })
    fireEvent.click(sendBtn)

    expect(await screen.findByText(/请求失败/)).toBeInTheDocument()
    expect(screen.getByText(/网络错误/)).toBeInTheDocument()
  })

  it('toggles sidebar visibility', () => {
    render(<App />)
    // Sidebar is visible by default
    expect(screen.getByText('暂无历史会话')).toBeInTheDocument()
    // Click toggle button
    fireEvent.click(screen.getByLabelText('切换侧栏'))
    // Sidebar should be hidden
    expect(screen.queryByText('暂无历史会话')).not.toBeInTheDocument()
  })

  it('toggles config panel visibility', () => {
    render(<App />)
    // Config panel is visible by default
    expect(screen.getByText('LLM 提供商')).toBeInTheDocument()
    // Click toggle button
    fireEvent.click(screen.getByLabelText('切换配置面板'))
    // Config panel should be hidden
    expect(screen.queryByText('LLM 提供商')).not.toBeInTheDocument()
  })

  it('shows error toast when loadSessions fails', async () => {
    mockApi.getSessions.mockRejectedValue(new Error('连接被拒绝'))

    render(<App />)
    // The error should be displayed as a toast (called during init)
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
    const input = screen.getByPlaceholderText('输入你的问题…')

    fireEvent.change(input, { target: { value: 'Ctrl+Enter 发送测试' } })
    fireEvent.keyDown(input, { key: 'Enter', ctrlKey: true })

    expect(await screen.findByText('Ctrl+Enter 发送测试')).toBeInTheDocument()
  })
})
