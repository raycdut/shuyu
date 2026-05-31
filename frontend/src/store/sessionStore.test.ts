import { describe, it, expect, beforeEach } from 'vitest'
import { useSessionStore } from './sessionStore'
import type { Session, Message } from '../types'

describe('sessionStore', () => {
  beforeEach(() => {
    useSessionStore.setState({
      sessions: [],
      activeSessionId: null,
      messages: [],
      isLoading: false,
    })
  })

  it('starts with empty default state', () => {
    const state = useSessionStore.getState()
    expect(state.sessions).toEqual([])
    expect(state.activeSessionId).toBeNull()
    expect(state.messages).toEqual([])
    expect(state.isLoading).toBe(false)
  })

  it('sets sessions list', () => {
    const sessions: Session[] = [
      { id: 's1', title: '会话1', messages: 3 },
      { id: 's2', title: '会话2', messages: 5 },
    ]
    useSessionStore.getState().setSessions(sessions)
    expect(useSessionStore.getState().sessions).toEqual(sessions)
  })

  it('sets active session id', () => {
    useSessionStore.getState().setActiveSessionId('s1')
    expect(useSessionStore.getState().activeSessionId).toBe('s1')
  })

  it('sets active session id to null', () => {
    useSessionStore.getState().setActiveSessionId('s1')
    useSessionStore.getState().setActiveSessionId(null)
    expect(useSessionStore.getState().activeSessionId).toBeNull()
  })

  it('sets messages array directly', () => {
    const messages: Message[] = [
      { id: 'm1', role: 'user', content: '你好' },
    ]
    useSessionStore.getState().setMessages(messages)
    expect(useSessionStore.getState().messages).toEqual(messages)
  })

  it('appends messages via updater function', () => {
    useSessionStore.getState().setMessages([
      { id: 'm1', role: 'user', content: '你好' },
    ])
    useSessionStore.getState().setMessages((prev) => [
      ...prev,
      { id: 'm2', role: 'assistant', content: '你好！有什么可以帮助你的？' },
    ])
    const messages = useSessionStore.getState().messages
    expect(messages).toHaveLength(2)
    expect(messages[0].content).toBe('你好')
    expect(messages[1].content).toBe('你好！有什么可以帮助你的？')
  })

  it('sets loading state', () => {
    useSessionStore.getState().setIsLoading(true)
    expect(useSessionStore.getState().isLoading).toBe(true)

    useSessionStore.getState().setIsLoading(false)
    expect(useSessionStore.getState().isLoading).toBe(false)
  })
})
