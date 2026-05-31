import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useSessions } from './useSessions'
import type { Session, Message } from '../types'

const mockSessionState = vi.hoisted(() => ({
  sessions: [] as Session[],
  activeSessionId: null as string | null,
  messages: [] as Message[],
  isLoading: false,
  setSessions: vi.fn(),
  setActiveSessionId: vi.fn(),
  setMessages: vi.fn(),
  setIsLoading: vi.fn(),
}))

const mockUIState = vi.hoisted(() => ({
  leftOpen: true,
  error: null as string | null,
  setError: vi.fn(),
  setLeftOpen: vi.fn(),
}))

const mockApi = vi.hoisted(() => ({
  getSessions: vi.fn(),
  getSessionMessages: vi.fn(),
  renameSession: vi.fn(),
  deleteSession: vi.fn(),
}))

vi.mock('../store/sessionStore', () => ({
  useSessionStore: Object.assign(
    vi.fn((selector?: any) => {
      return selector ? selector(mockSessionState) : mockSessionState
    }),
    { getState: vi.fn(() => mockSessionState) }
  ),
}))

vi.mock('../store/uiStore', () => ({
  useUIStore: Object.assign(
    vi.fn((selector?: any) => {
      return selector ? selector(mockUIState) : mockUIState
    }),
    { getState: vi.fn(() => mockUIState) }
  ),
}))

vi.mock('../api', () => ({
  api: mockApi,
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}))

describe('useSessions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSessionState.activeSessionId = null
  })

  it('loadSessions - calls api.getSessions and updates store', async () => {
    const sessions: Session[] = [
      { id: 's1', title: '会话1', messages: 5 },
      { id: 's2', title: '会话2', messages: 3 },
    ]
    mockApi.getSessions.mockResolvedValue({ sessions })

    const { result } = renderHook(() => useSessions())

    await act(async () => {
      await result.current.loadSessions()
    })

    expect(mockApi.getSessions).toHaveBeenCalled()
    expect(mockSessionState.setSessions).toHaveBeenCalledWith(sessions)
  })

  it('loadSessions handles errors gracefully', async () => {
    const error = new Error('Network error')
    mockApi.getSessions.mockRejectedValue(error)

    const { result } = renderHook(() => useSessions())

    await act(async () => {
      await result.current.loadSessions()
    })

    expect(mockUIState.setError).toHaveBeenCalledWith('session.loadFailed: Network error')
  })

  it('loadSessions defaults to empty array when sessions is undefined', async () => {
    mockApi.getSessions.mockResolvedValue({})

    const { result } = renderHook(() => useSessions())

    await act(async () => {
      await result.current.loadSessions()
    })

    expect(mockSessionState.setSessions).toHaveBeenCalledWith([])
  })

  it('handleSelectSession - calls api.getSessionMessages, sets activeSessionId and messages', async () => {
    const messages = [
      { role: 'user' as const, content: 'Hello' },
    ]
    mockApi.getSessionMessages.mockResolvedValue({ messages })

    const { result } = renderHook(() => useSessions())

    await act(async () => {
      await result.current.handleSelectSession('s1')
    })

    expect(mockSessionState.setActiveSessionId).toHaveBeenCalledWith('s1')
    expect(mockApi.getSessionMessages).toHaveBeenCalledWith('s1')
    expect(mockSessionState.setMessages).toHaveBeenCalledWith([
      { id: 'msg_s1_0', role: 'user', content: 'Hello' },
    ])
  })

  it('handleSelectSession preserves existing message id', async () => {
    const messages = [
      { id: 'custom_id', role: 'assistant' as const, content: 'Response' },
    ]
    mockApi.getSessionMessages.mockResolvedValue({ messages })

    const { result } = renderHook(() => useSessions())

    await act(async () => {
      await result.current.handleSelectSession('s1')
    })

    expect(mockSessionState.setMessages).toHaveBeenCalledWith([
      { id: 'custom_id', role: 'assistant', content: 'Response' },
    ])
  })

  it('handleSelectSession defaults to empty array when messages is undefined', async () => {
    mockApi.getSessionMessages.mockResolvedValue({})

    const { result } = renderHook(() => useSessions())

    await act(async () => {
      await result.current.handleSelectSession('s1')
    })

    expect(mockSessionState.setActiveSessionId).toHaveBeenCalledWith('s1')
    expect(mockSessionState.setMessages).toHaveBeenCalledWith([])
  })

  it('handleSelectSession handles errors (sets empty messages)', async () => {
    mockApi.getSessionMessages.mockRejectedValue(new Error('Failed'))

    const { result } = renderHook(() => useSessions())

    await act(async () => {
      await result.current.handleSelectSession('s1')
    })

    expect(mockSessionState.setActiveSessionId).toHaveBeenCalledWith('s1')
    expect(mockSessionState.setMessages).toHaveBeenCalledWith([])
  })

  it('handleNewSession - clears active session and messages', () => {
    const { result } = renderHook(() => useSessions())

    act(() => {
      result.current.handleNewSession()
    })

    expect(mockSessionState.setActiveSessionId).toHaveBeenCalledWith(null)
    expect(mockSessionState.setMessages).toHaveBeenCalledWith([])
  })

  it('handleRenameSession - calls api.renameSession and reloads', async () => {
    mockApi.renameSession.mockResolvedValue(undefined)
    const sessions = [{ id: 's1', title: 'renamed', messages: 3 }] as Session[]
    mockApi.getSessions.mockResolvedValue({ sessions })

    const { result } = renderHook(() => useSessions())

    await act(async () => {
      await result.current.handleRenameSession('s1', 'renamed')
    })

    expect(mockApi.renameSession).toHaveBeenCalledWith('s1', 'renamed')
    expect(mockApi.getSessions).toHaveBeenCalled()
    expect(mockSessionState.setSessions).toHaveBeenCalledWith(sessions)
  })

  it('handleRenameSession handles errors', async () => {
    mockApi.renameSession.mockRejectedValue(new Error('Rename failed'))

    const { result } = renderHook(() => useSessions())

    await act(async () => {
      await result.current.handleRenameSession('s1', 'renamed')
    })

    expect(mockUIState.setError).toHaveBeenCalledWith('session.renameFailed: Rename failed')
  })

  it('handleDeleteSession - calls api.deleteSession and reloads', async () => {
    mockSessionState.activeSessionId = 's1'
    mockApi.deleteSession.mockResolvedValue(undefined)
    const sessions = [{ id: 's2', title: 'remaining', messages: 2 }] as Session[]
    mockApi.getSessions.mockResolvedValue({ sessions })

    const { result } = renderHook(() => useSessions())

    await act(async () => {
      await result.current.handleDeleteSession('s2')
    })

    expect(mockApi.deleteSession).toHaveBeenCalledWith('s2')
    expect(mockSessionState.setActiveSessionId).not.toHaveBeenCalledWith(null)
    expect(mockApi.getSessions).toHaveBeenCalled()
    expect(mockSessionState.setSessions).toHaveBeenCalledWith(sessions)
  })

  it('handleDeleteSession - handles deleting active session', async () => {
    mockSessionState.activeSessionId = 's1'
    mockApi.deleteSession.mockResolvedValue(undefined)
    const sessions = [{ id: 's2', title: 'remaining', messages: 2 }] as Session[]
    mockApi.getSessions.mockResolvedValue({ sessions })

    const { result } = renderHook(() => useSessions())

    await act(async () => {
      await result.current.handleDeleteSession('s1')
    })

    expect(mockApi.deleteSession).toHaveBeenCalledWith('s1')
    expect(mockSessionState.setActiveSessionId).toHaveBeenCalledWith(null)
    expect(mockSessionState.setMessages).toHaveBeenCalledWith([])
    expect(mockApi.getSessions).toHaveBeenCalled()
    expect(mockSessionState.setSessions).toHaveBeenCalledWith(sessions)
  })

  it('handleDeleteSession handles errors', async () => {
    mockApi.deleteSession.mockRejectedValue(new Error('Delete failed'))

    const { result } = renderHook(() => useSessions())

    await act(async () => {
      await result.current.handleDeleteSession('s1')
    })

    expect(mockUIState.setError).toHaveBeenCalledWith('session.deleteFailed: Delete failed')
  })

  it('handleClearAllSessions - calls clear endpoint and reloads', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true } as Response)
    const sessions = [] as Session[]
    mockApi.getSessions.mockResolvedValue({ sessions })

    const { result } = renderHook(() => useSessions())

    await act(async () => {
      await result.current.handleClearAllSessions()
    })

    expect(mockSessionState.setActiveSessionId).toHaveBeenCalledWith(null)
    expect(mockSessionState.setMessages).toHaveBeenCalledWith([])
    expect(global.fetch).toHaveBeenCalledWith('/api/sessions/clear', { method: 'POST' })
    expect(mockApi.getSessions).toHaveBeenCalled()
    expect(mockSessionState.setSessions).toHaveBeenCalledWith(sessions)
  })

  it('handleClearAllSessions handles fetch failure', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Clear failed'))
    const sessions = [{ id: 's1', title: 'after clear', messages: 0 }] as Session[]
    mockApi.getSessions.mockResolvedValue({ sessions })

    const { result } = renderHook(() => useSessions())

    await act(async () => {
      await result.current.handleClearAllSessions()
    })

    expect(mockSessionState.setActiveSessionId).toHaveBeenCalledWith(null)
    expect(mockSessionState.setMessages).toHaveBeenCalledWith([])
    expect(mockUIState.setError).toHaveBeenCalledWith('session.clearFailed: Clear failed')
    expect(mockApi.getSessions).toHaveBeenCalled()
    expect(mockSessionState.setSessions).toHaveBeenCalledWith(sessions)
  })

  it('handleClearAllSessions handles non-ok response', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 } as Response)
    const sessions = [] as Session[]
    mockApi.getSessions.mockResolvedValue({ sessions })

    const { result } = renderHook(() => useSessions())

    await act(async () => {
      await result.current.handleClearAllSessions()
    })

    expect(mockUIState.setError).toHaveBeenCalledWith('session.clearFailed: HTTP 500')
    expect(mockApi.getSessions).toHaveBeenCalled()
    expect(mockSessionState.setSessions).toHaveBeenCalledWith(sessions)
  })

  it('returns all handler functions', () => {
    const { result } = renderHook(() => useSessions())

    expect(result.current).toHaveProperty('loadSessions')
    expect(result.current).toHaveProperty('handleSelectSession')
    expect(result.current).toHaveProperty('handleNewSession')
    expect(result.current).toHaveProperty('handleRenameSession')
    expect(result.current).toHaveProperty('handleDeleteSession')
    expect(result.current).toHaveProperty('handleClearAllSessions')
    expect(typeof result.current.loadSessions).toBe('function')
    expect(typeof result.current.handleSelectSession).toBe('function')
    expect(typeof result.current.handleNewSession).toBe('function')
    expect(typeof result.current.handleRenameSession).toBe('function')
    expect(typeof result.current.handleDeleteSession).toBe('function')
    expect(typeof result.current.handleClearAllSessions).toBe('function')
  })
})
