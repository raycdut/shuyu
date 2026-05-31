import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import IndexPage from './IndexPage'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual as any,
    useNavigate: () => mockNavigate,
  }
})

let mockUser: any = { id: '1', username: 'admin', role: 'admin' as const, is_active: true }
let mockDatabases: any[] = []
let mockLlmConnected: boolean | null = null
let mockLlmConfig: any = { provider: 'openai', model: 'gpt-4o', name: 'GPT-4o', api_key: '', api_base: '', timeout: 60 }
let mockSessions: any[] = []

vi.mock('../store/authStore', () => ({
  useAuthStore: Object.assign(
    vi.fn((selector?: any) => {
      const state = { user: mockUser }
      return selector ? selector(state) : state
    }),
    { getState: vi.fn(() => ({ user: mockUser })) }
  ),
}))

vi.mock('../store/configStore', () => ({
  useConfigStore: Object.assign(
    vi.fn((selector?: any) => {
      const state = {
        databases: mockDatabases,
        llmConnected: mockLlmConnected,
        llmConfig: mockLlmConfig,
      }
      return selector ? selector(state) : state
    }),
    { getState: vi.fn(() => ({})) }
  ),
}))

vi.mock('../store/sessionStore', () => ({
  useSessionStore: Object.assign(
    vi.fn((selector?: any) => {
      const state = { sessions: mockSessions }
      return selector ? selector(state) : state
    }),
    { getState: vi.fn(() => ({})) }
  ),
}))

function renderIndexPage() {
  return render(
    <MemoryRouter>
      <IndexPage />
    </MemoryRouter>
  )
}

describe('IndexPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUser = { id: '1', username: 'admin', role: 'admin' as const, is_active: true }
    mockDatabases = [{ id: 'db1', name: 'TestDB', type: 'duckdb' }]
    mockLlmConnected = true
    mockLlmConfig = { provider: 'openai', model: 'gpt-4o', name: 'GPT-4o', api_key: '', api_base: '', timeout: 60 }
    mockSessions = [{ id: 's1', title: 'Session 1', messages: 5 }]
  })

  it('renders the brand name and tagline', () => {
    renderIndexPage()
    const names = screen.getAllByText('数语')
    expect(names.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('问你的数据')).toBeInTheDocument()
  })

  it('renders the description text', () => {
    renderIndexPage()
    expect(screen.getByText(/连接你的数据库/)).toBeInTheDocument()
  })

  it('renders feature cards for admin users', () => {
    renderIndexPage()
    const names = screen.getAllByText('数语')
    expect(names.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('系统管理')).toBeInTheDocument()
  })

  it('does not show admin card for non-admin users', () => {
    mockUser = { id: '2', username: 'user', role: 'user' as const, is_active: true }
    renderIndexPage()
    const names = screen.getAllByText('数语')
    expect(names.length).toBeGreaterThanOrEqual(1)
    expect(screen.queryByText('系统管理')).not.toBeInTheDocument()
  })

  it('navigates to /chat when clicking chat card button', () => {
    renderIndexPage()
    const buttons = screen.getAllByRole('button', { name: '开始对话' })
    expect(buttons.length).toBeGreaterThanOrEqual(1)
    fireEvent.click(buttons[0])
    expect(mockNavigate).toHaveBeenCalledWith('/chat')
  })

  it('navigates to /chat when clicking the chat card', () => {
    renderIndexPage()
    const chatCard = screen.getAllByText('数语')[0].closest('div[class*="cursor-pointer"]')
    if (chatCard) {
      fireEvent.click(chatCard)
      expect(mockNavigate).toHaveBeenCalledWith('/chat')
    }
  })

  it('navigates to /admin when clicking admin card', () => {
    renderIndexPage()
    const buttons = screen.getAllByRole('button', { name: '前往管理' })
    expect(buttons.length).toBeGreaterThanOrEqual(1)
    fireEvent.click(buttons[0])
    expect(mockNavigate).toHaveBeenCalledWith('/admin')
  })

  it('shows database count', () => {
    renderIndexPage()
    const ones = screen.getAllByText('1')
    expect(ones.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('已连接数据库')).toBeInTheDocument()
  })

  it('shows LLM connection status', () => {
    renderIndexPage()
    expect(screen.getByText('已连接')).toBeInTheDocument()
    expect(screen.getByText(/gpt-4o/)).toBeInTheDocument()
  })

  it('shows LLM as disconnected when not connected', () => {
    mockLlmConnected = false
    renderIndexPage()
    expect(screen.getByText('未连接')).toBeInTheDocument()
  })

  it('shows session count', () => {
    renderIndexPage()
    const ones = screen.getAllByText('1')
    expect(ones.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('历史会话')).toBeInTheDocument()
  })

  it('shows zero counts when no data', () => {
    mockDatabases = []
    mockSessions = []
    renderIndexPage()
    const zeroElements = screen.getAllByText('0')
    expect(zeroElements.length).toBeGreaterThanOrEqual(1)
  })
})
