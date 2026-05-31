import { create } from 'zustand'
import { Session, Message } from '../types'

/**
 * 会话管理状态接口
 */
interface SessionState {
  /** 会话列表 */
  sessions: Session[]
  /** 当前激活的会话 ID */
  activeSessionId: string | null
  /** 当前会话的消息列表 */
  messages: Message[]
  /** 加载状态 */
  isLoading: boolean

  /** 设置会话列表 */
  setSessions: (sessions: Session[]) => void
  /** 设置当前激活的会话 ID */
  setActiveSessionId: (id: string | null) => void
  /**
   * 设置消息列表
   * 支持直接传入数组或通过函数基于前一次值更新
   */
  setMessages: (messages: Message[] | ((prev: Message[]) => Message[])) => void
  /** 设置加载状态 */
  setIsLoading: (loading: boolean) => void
}

/**
 * 会话管理 Zustand Store
 * 管理会话列表、当前会话消息和加载状态
 */
export const useSessionStore = create<SessionState>((set) => ({
  sessions: [],
  activeSessionId: null,
  messages: [],
  isLoading: false,

  setSessions: (sessions) => set({ sessions }),
  setActiveSessionId: (activeSessionId) => set({ activeSessionId }),
  setMessages: (messages) => set((state) => ({
    messages: typeof messages === 'function' ? messages(state.messages) : messages
  })),
  setIsLoading: (isLoading) => set({ isLoading }),
}))
