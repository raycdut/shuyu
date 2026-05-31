import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import Sidebar from './Sidebar'
import type { Session, DatabaseInfo } from '../types'

// Mock child modals
vi.mock('./DBConfigModal', () => ({
  default: ({ open }: { open: boolean }) => open ? <div data-testid="db-config-modal">DBConfigModal</div> : null,
}))

const makeSessions = (): Session[] => [
  { id: 's1', title: '本月销售分析', messages: 5, last_active: Date.now() / 1000 - 100 },
  { id: 's2', title: '用户画像', messages: 3, last_active: Date.now() / 1000 - 200 },
  { id: 's3', title: '上周趋势', messages: 8, last_active: Date.now() / 1000 - 86400 * 3 },
]

const makeDatabases = (): DatabaseInfo[] => [
  { id: 'db1', name: '零售数据库', type: 'duckdb', is_active: true },
  { id: 'db2', name: '日志库', type: 'clickhouse' },
]

const defaultProps = {
  open: true,
  sessions: [],
  activeSessionId: null as string | null,
  databases: [],
  activeDbId: null as string | null,
  onSelectSession: vi.fn(),
  onNewSession: vi.fn(),
  onRenameSession: vi.fn(),
  onDeleteSession: vi.fn(),
  onSelectDb: vi.fn(),
  onDatabasesChange: vi.fn(),
}

describe('Sidebar', () => {
  it('renders nothing when closed', () => {
    const { container } = render(<Sidebar {...defaultProps} open={false} />)
    expect(container.innerHTML).toBe('')
  })

  it('shows empty state when no sessions', () => {
    render(<Sidebar {...defaultProps} />)
    expect(screen.getByText('暂无历史会话')).toBeInTheDocument()
  })

  it('shows empty database prompt when no databases', () => {
    render(<Sidebar {...defaultProps} />)
    expect(screen.getByText('尚未添加数据库')).toBeInTheDocument()
  })

  it('renders session list grouped by time', () => {
    const sessions = makeSessions()
    render(<Sidebar {...defaultProps} sessions={sessions} />)
    expect(screen.getByText('今天')).toBeInTheDocument()
    expect(screen.getByText('本周')).toBeInTheDocument()
    expect(screen.getByText('本月销售分析')).toBeInTheDocument()
    expect(screen.getByText('上周趋势')).toBeInTheDocument()
  })

  it('shows message count for each session', () => {
    const sessions = makeSessions()
    render(<Sidebar {...defaultProps} sessions={sessions} />)
    // Message count badges
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('calls onSelectSession when clicking a session', () => {
    const onSelect = vi.fn()
    const sessions = makeSessions()
    render(<Sidebar {...defaultProps} sessions={sessions} onSelectSession={onSelect} />)
    fireEvent.click(screen.getByText('本月销售分析'))
    expect(onSelect).toHaveBeenCalledWith('s1')
  })

  it('calls onNewSession when clicking the new button', () => {
    const onNew = vi.fn()
    render(<Sidebar {...defaultProps} onNewSession={onNew} />)
    fireEvent.click(screen.getByLabelText('新建会话'))
    expect(onNew).toHaveBeenCalled()
  })

  it('renders database list', () => {
    const dbs = makeDatabases()
    render(<Sidebar {...defaultProps} databases={dbs} />)
    expect(screen.getByText('零售数据库')).toBeInTheDocument()
    expect(screen.getByText('日志库')).toBeInTheDocument()
  })

  it('highlights the active session', () => {
    const sessions = makeSessions()
    render(<Sidebar {...defaultProps} sessions={sessions} activeSessionId="s1" />)
    const btn = screen.getByText('本月销售分析').closest('button')
    expect(btn?.className).toContain('bg-celadon')
  })

  it('renders database tree on click', async () => {
    // Mock the API for this test
    const { api } = await import('../api')
    vi.spyOn(api, 'getDatabaseTables').mockResolvedValue({
      tables: [{ name: 'orders', columns: [{ name: 'id', type: 'INT' }] }],
    })

    const dbs = makeDatabases()
    render(<Sidebar {...defaultProps} databases={dbs} />)
    // Click on first database to expand
    fireEvent.click(screen.getByText('零售数据库'))
    // Should show table names eventually
    expect(await screen.findByText('orders')).toBeInTheDocument()
  })
})
