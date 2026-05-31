import { useCallback } from 'react'
import { useSessionStore } from '../store/sessionStore'
import { useUIStore } from '../store/uiStore'
import { api } from '../api'

/**
 * 会话管理 Hook
 * 负责会话的增删改查逻辑
 */
export function useSessions() {
  const setSessions = useSessionStore(s => s.setSessions)
  const setActiveSessionId = useSessionStore(s => s.setActiveSessionId)
  const setMessages = useSessionStore(s => s.setMessages)
  const activeSessionId = useSessionStore(s => s.activeSessionId)

  const setError = useUIStore(s => s.setError)

  /**
   * 加载所有会话
   */
  const loadSessions = useCallback(async () => {
    console.log('[Sessions] 正在加载会话列表...')
    try {
      const data = await api.getSessions()
      setSessions(data.sessions || [])
      console.log(`[Sessions] 加载完成，共 ${data.sessions?.length || 0} 个会话`)
    } catch (err: any) {
      console.error('[Sessions] 加载失败', err)
      setError(`加载会话失败: ${err.message || '未知错误'}`)
    }
  }, [setSessions, setError])

  /**
   * 选择会话
   */
  const handleSelectSession = useCallback(async (sessionId: string) => {
    console.log(`[Sessions] 切换到会话: ${sessionId}`)
    setActiveSessionId(sessionId)
    try {
      const data = await api.getSessionMessages(sessionId)
      console.log(`[Sessions] 会话消息加载完成，共 ${data.messages?.length || 0} 条`)
      // 为加载的消息分配 ID，确保 React 列表渲染的唯一性
      const msgs = (data.messages || []).map((m, i) => ({
        ...m,
        id: m.id || `msg_${sessionId}_${i}`
      }))
      setMessages(msgs)
    } catch (err: any) {
      console.error('[Sessions] 消息加载失败', err)
      setMessages([])
    }
  }, [setActiveSessionId, setMessages])

  /**
   * 新建会话
   */
  const handleNewSession = useCallback(() => {
    setActiveSessionId(null)
    setMessages([])
  }, [setActiveSessionId, setMessages])

  /**
   * 重命名会话
   */
  const handleRenameSession = useCallback(async (sessionId: string, title: string) => {
    try {
      await api.renameSession(sessionId, title)
      await loadSessions()
    } catch (err: any) {
      setError(`重命名失败: ${err.message || '未知错误'}`)
    }
  }, [loadSessions, setError])

  /**
   * 删除会话
   */
  const handleDeleteSession = useCallback(async (sessionId: string) => {
    try {
      await api.deleteSession(sessionId)
      if (activeSessionId === sessionId) {
        handleNewSession()
      }
      await loadSessions()
    } catch (err: any) {
      setError(`删除会话失败: ${err.message || '未知错误'}`)
    }
  }, [activeSessionId, handleNewSession, loadSessions, setError])

  /**
   * 清空所有会话
   */
  const handleClearAllSessions = useCallback(async () => {
    handleNewSession()
    try {
      const res = await fetch('/api/sessions/clear', { method: 'POST' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      await loadSessions()
    } catch (err: any) {
      setError(`清空会话失败: ${err.message || '未知错误'}`)
      await loadSessions()
    }
  }, [handleNewSession, loadSessions, setError])

  return {
    loadSessions,
    handleSelectSession,
    handleNewSession,
    handleRenameSession,
    handleDeleteSession,
    handleClearAllSessions,
  }
}
