import { useEffect, useCallback } from 'react'
import { useSessionStore } from '../store/sessionStore'
import { useConfigStore } from '../store/configStore'
import { useUIStore } from '../store/uiStore'
import { useSessions } from '../hooks/useSessions'
import { useChatStream } from '../hooks/useChatStream'
import { api } from '../api'
import Sidebar from '../components/Sidebar'
import Chat from '../components/Chat'

/**
 * 聊天页面组件
 * 包含侧边栏（会话列表 + 数据库管理）和聊天主区域的并列布局。
 * 会话管理和消息流处理分别通过 useSessions 和 useChatStream hooks 实现。
 */
export default function ChatPage() {
  // 使用选择器按需订阅 Store，提高组件性能
  const sessions = useSessionStore(s => s.sessions)
  const activeSessionId = useSessionStore(s => s.activeSessionId)
  const messages = useSessionStore(s => s.messages)
  const isLoading = useSessionStore(s => s.isLoading)

  const databases = useConfigStore(s => s.databases)
  const activeDbId = useConfigStore(s => s.activeDbId)
  const mode = useConfigStore(s => s.mode)
  const schema = useConfigStore(s => s.schema)
  const setActiveDbId = useConfigStore(s => s.setActiveDbId)
  const setMode = useConfigStore(s => s.setMode)
  const setDatabases = useConfigStore(s => s.setDatabases)

  const leftOpen = useUIStore(s => s.leftOpen)
  const setError = useUIStore(s => s.setError)

  const {
    loadSessions,
    handleSelectSession,
    handleNewSession,
    handleRenameSession,
    handleDeleteSession,
    handleClearAllSessions,
  } = useSessions()

  const { handleSendMessage } = useChatStream()

  /**
   * 加载数据库列表
   */
  const loadDatabases = useCallback(async () => {
    try {
      const data = await api.getDatabases()
      setDatabases(data.databases || [])
    } catch (err: any) {
      setError(`加载数据库列表失败: ${err.message || '未知错误'}`)
    }
  }, [setDatabases, setError])

  useEffect(() => {
    loadSessions()
  }, [loadSessions])

  return (
    <div className="flex-1 flex overflow-hidden">
      <Sidebar
        open={leftOpen}
        sessions={sessions}
        activeSessionId={activeSessionId}
        databases={databases}
        activeDbId={activeDbId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onRenameSession={handleRenameSession}
        onDeleteSession={handleDeleteSession}
        onSelectDb={setActiveDbId}
        onDatabasesChange={loadDatabases}
        onClearAllSessions={handleClearAllSessions}
      />

      {leftOpen && <div className="w-px bg-tea flex-shrink-0" />}

      <Chat
        messages={messages}
        isLoading={isLoading}
        onSend={handleSendMessage}
        schema={schema}
        mode={mode}
        onModeChange={setMode}
      />
    </div>
  )
}
