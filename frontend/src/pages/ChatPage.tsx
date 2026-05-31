import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useSessionStore } from '../store/sessionStore'
import { useConfigStore } from '../store/configStore'
import { useUIStore } from '../store/uiStore'
import { useSessions } from '../hooks/useSessions'
import { useChatStream } from '../hooks/useChatStream'
import Sidebar from '../components/Sidebar'
import Chat from '../components/Chat'

/**
 * 聊天页面组件
 * 包含侧边栏（会话列表 + 数据库管理）和聊天主区域的并列布局。
 * 会话管理和消息流处理分别通过 useSessions 和 useChatStream hooks 实现。
 */
export default function ChatPage() {
  const { t } = useTranslation()
  const messages = useSessionStore(s => s.messages)
  const isLoading = useSessionStore(s => s.isLoading)

  const schema = useConfigStore(s => s.schema)
  const mode = useConfigStore(s => s.mode)
  const setMode = useConfigStore(s => s.setMode)

  const leftOpen = useUIStore(s => s.leftOpen)

  const { loadSessions } = useSessions()

  const { handleSendMessage } = useChatStream()

  useEffect(() => {
    loadSessions()
  }, [loadSessions])

  return (
    <div className="flex-1 flex overflow-hidden">
      <Sidebar open={leftOpen} />

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
