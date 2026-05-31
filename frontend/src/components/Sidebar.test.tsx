import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import Sidebar from './Sidebar'
import { useSessionStore } from '../store/sessionStore'
import { useConfigStore } from '../store/configStore'
import { useUIStore } from '../store/uiStore'
import type { Session, DatabaseInfo } from '../types'

vi.mock('./DBConfigModal', () => ({
  default: ({ open }: { open: boolean }) => open ? <div data-testid="db-config-modal">DBConfigModal</div> : null,
}))

vi.mock('../hooks/useSessions', () => ({
  useSessions: () => ({
    handleSelectSession: mockSelectSession,
    handleNewSession: mockNewSession,
    handleRenameSession: mockRenameSession,
    handleDeleteSession: mockDeleteSession,
    handleClearAllSessions: mockClearAllSessions,
  }),
}))

const mockSelectSession = vi.fn()
const mockNewSession = vi.fn()
const mockRenameSession = vi.fn()
const mockDeleteSession = vi.fn()
const mockClearAllSessions = vi.fn()

const makeSessions = (): Session[] => [
  { id: 's1', title: '本月销售分析', messages: 5, last_active: Date.now() / 1000 - 100 },
  { id: 's2', title: '用户画像', messages: 3, last_active: Date.now() / 1000 - 200 },
  { id: 's3', title: '上周趋势', messages: 8, last_active: Date.now() / 1000 - 86400 * 3 },
]

const makeDatabases = (): DatabaseInfo[] => [
  { id: 'db1', name: '零售数据库', type: 'duckdb', is_active: true },
  { id: 'db2', name: '日志库', type: 'clickhouse' },
]

beforeEach(() => {
  vi.clearAllMocks()
  useSessionStore.setState({
    sessions: [],
    activeSessionId: null,
    messages: [],
    isLoading: false,
  })
  useConfigStore.setState({
    databases: [],
    activeDbId: null,
  })
  useUIStore.setState({
    leftOpen: true,
    error: null,
  })
})

describe('Sidebar', () => {
  it('renders nothing when closed', () => {
    const { container } = render(<Sidebar open={false} />)
    expect(container.innerHTML).toBe('')
  })

  it('shows empty state when no sessions', () => {
    render(<Sidebar open={true} />)
    expect(screen.getByText('暂无历史会话')).toBeInTheDocument()
  })

  it('shows empty database prompt when no databases', () => {
    render(<Sidebar open={true} />)
    expect(screen.getByText('尚未添加数据库')).toBeInTheDocument()
  })

  it('renders session list grouped by time', () => {
    const sessions = makeSessions()
    useSessionStore.setState({ sessions })
    render(<Sidebar open={true} />)
    expect(screen.getByText('今天')).toBeInTheDocument()
    expect(screen.getByText('本周')).toBeInTheDocument()
    expect(screen.getByText('本月销售分析')).toBeInTheDocument()
    expect(screen.getByText('上周趋势')).toBeInTheDocument()
  })

  it('shows message count for each session', () => {
    const sessions = makeSessions()
    useSessionStore.setState({ sessions })
    render(<Sidebar open={true} />)
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('calls handleSelectSession when clicking a session', () => {
    const sessions = makeSessions()
    useSessionStore.setState({ sessions })
    render(<Sidebar open={true} />)
    fireEvent.click(screen.getByText('本月销售分析'))
    expect(mockSelectSession).toHaveBeenCalledWith('s1')
  })

  it('calls handleNewSession when clicking the new button', () => {
    render(<Sidebar open={true} />)
    fireEvent.click(screen.getByLabelText('新建会话'))
    expect(mockNewSession).toHaveBeenCalled()
  })

  it('renders database list', () => {
    const dbs = makeDatabases()
    useConfigStore.setState({ databases: dbs })
    render(<Sidebar open={true} />)
    expect(screen.getByText('零售数据库')).toBeInTheDocument()
    expect(screen.getByText('日志库')).toBeInTheDocument()
  })

  it('highlights the active session', () => {
    const sessions = makeSessions()
    useSessionStore.setState({ sessions, activeSessionId: 's1' })
    render(<Sidebar open={true} />)
    const btn = screen.getByText('本月销售分析').closest('button')
    expect(btn?.className).toContain('bg-celadon')
  })

  it('renders database tree on click', async () => {
    const { api } = await import('../api')
    vi.spyOn(api, 'getDatabaseTables').mockResolvedValue({
      tables: [{ name: 'orders', columns: [{ name: 'id', type: 'INT' }] }],
    })

    const dbs = makeDatabases()
    useConfigStore.setState({ databases: dbs })
    render(<Sidebar open={true} />)
    fireEvent.click(screen.getByText('零售数据库'))
    expect(await screen.findByText('orders')).toBeInTheDocument()
  })
})
