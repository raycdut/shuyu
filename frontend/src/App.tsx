import { useState, useEffect, useCallback } from 'react'
import Sidebar from './components/Sidebar'
import Chat from './components/Chat'
import ConfigPanel from './components/ConfigPanel'
import StatusBar from './components/StatusBar'
import { Session, DatabaseInfo, LLMConfig, SafetyConfig, Message } from './types'
import { api } from './api'

export default function App() {
  // --- 状态 ---
  const [sessions, setSessions] = useState<Session[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)

  // 数据库
  const [databases, setDatabases] = useState<DatabaseInfo[]>([])
  const [activeDbId, setActiveDbId] = useState<string | null>(null)
  const [schema, setSchema] = useState<{ name: string; columns: { name: string; type: string }[] }[]>([])

  // LLM 连接状态
  const [llmConnected, setLlmConnected] = useState<boolean | null>(null)

  // 配置
  const [llmConfig, setLLMConfig] = useState<LLMConfig>({
    provider: 'openai',
    model: 'gpt-4o',
    api_key: '',
    api_base: '',
  })
  const [safetyConfig, setSafetyConfig] = useState<SafetyConfig>({
    read_only: true,
    require_approval: true,
    max_rows: 1000,
  })

  // 面板展开
  const [leftOpen, setLeftOpen] = useState(true)
  const [rightOpen, setRightOpen] = useState(true)

  // --- 初始化 ---
  useEffect(() => {
    loadSessions()
    loadSchema()
    loadDatabases()
    loadConfig()
    checkLLM()
  }, [])

  // --- LLM 连接检查 ---
  const checkLLM = useCallback(async () => {
    try {
      const res = await api.testLLM()
      setLlmConnected(res.ok)
    } catch {
      setLlmConnected(false)
    }
  }, [])

  // --- API 加载函数 ---
  const loadSessions = async () => {
    try {
      const data = await api.getSessions()
      setSessions(data.sessions || [])
    } catch { /* 静默失败 */ }
  }

  const loadSchema = async () => {
    try {
      const data = await api.getSchema()
      setSchema(data.tables || [])
    } catch { /* 静默失败 */ }
  }

  const loadDatabases = async () => {
    try {
      const data = await api.getDatabases()
      setDatabases(data.databases || [])
    } catch { /* 静默失败 */ }
  }

  const loadConfig = async () => {
    try {
      const data = await api.getConfig()
      if (data?.llm) setLLMConfig(prev => ({ ...prev, ...data.llm }))
      if (data?.safety) setSafetyConfig(prev => ({ ...prev, ...data.safety }))
    } catch { /* 静默失败 */ }
  }

  // --- 对话 ---
  const handleSendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return

    const userMsg: Message = { role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setIsLoading(true)

    try {
      const res = await api.sendMessage(text, activeSessionId ?? undefined, activeDbId ?? undefined)
      setActiveSessionId(res.session_id)

      const agentMsg: Message = {
        role: 'assistant',
        content: res.reply,
        tool_calls: res.tool_calls,
        sql_queries: res.sql_queries,
      }
      setMessages(prev => [...prev, agentMsg])
      loadSessions() // refresh session list
    } catch (err: any) {
      const errorMsg: Message = {
        role: 'assistant',
        content: `抱歉，请求失败：${err.message || '未知错误'}`,
      }
      setMessages(prev => [...prev, errorMsg])
    } finally {
      setIsLoading(false)
    }
  }, [activeSessionId, activeDbId, isLoading])

  // --- 选择会话 ---
  const handleSelectSession = async (sessionId: string) => {
    setActiveSessionId(sessionId)
    try {
      const data = await api.getSessionMessages(sessionId)
      setMessages(data.messages || [])
    } catch {
      setMessages([])
    }
  }

  // --- 新建会话 ---
  const handleNewSession = () => {
    setActiveSessionId(null)
    setMessages([])
  }

  // --- 重命名会话 ---
  const handleRenameSession = async (sessionId: string, title: string) => {
    try {
      await api.renameSession(sessionId, title)
      loadSessions()
    } catch { /* 静默 */ }
  }

  // --- 删除会话 ---
  const handleDeleteSession = async (sessionId: string) => {
    try {
      await api.deleteSession(sessionId)
      if (activeSessionId === sessionId) {
        setActiveSessionId(null)
        setMessages([])
      }
      loadSessions()
    } catch { /* 静默 */ }
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* ===== 顶部栏 ===== */}
      <header className="flex-shrink-0 flex items-center justify-between px-6 py-3 bg-white/80 backdrop-blur-sm ink-border border-t-0 border-x-0">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-song font-semibold text-ink tracking-wider">
            Data Chat
          </h1>
          <span className="text-xs text-ink-lighter font-kai">问你的数据</span>
        </div>
        <div className="flex items-center gap-4 text-ink-light">
          <button
            onClick={() => setLeftOpen(!leftOpen)}
            className={`p-1 rounded-sm transition-colors hover:bg-smoke ${leftOpen ? 'text-celadon' : ''}`}
            title="切换侧栏"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <line x1="9" y1="3" x2="9" y2="21" />
            </svg>
          </button>
          <button
            onClick={() => setRightOpen(!rightOpen)}
            className={`p-1 rounded-sm transition-colors hover:bg-smoke ${rightOpen ? 'text-celadon' : ''}`}
            title="切换配置面板"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3" />
              <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
            </svg>
          </button>
        </div>
      </header>

      {/* ===== 三栏主体 ===== */}
      <div className="flex-1 flex overflow-hidden">
        {/* 左栏 — 会话 + 数据库 */}
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
        />

        {/* 分隔线 */}
        {leftOpen && <div className="w-px bg-tea flex-shrink-0" />}

        {/* 中栏 — 聊天 */}
        <Chat
          messages={messages}
          isLoading={isLoading}
          onSend={handleSendMessage}
          schema={schema}
        />

        {/* 分隔线 */}
        {rightOpen && <div className="w-px bg-tea flex-shrink-0" />}

        {/* 右栏 — 配置 */}
        <ConfigPanel
          open={rightOpen}
          llmConfig={llmConfig}
          safetyConfig={safetyConfig}
          onLLMChange={setLLMConfig}
          onSafetyChange={setSafetyConfig}
          onConfigSave={() => { loadConfig(); checkLLM() }}
        />
      </div>

      {/* ===== 底部状态栏 ===== */}
      <StatusBar
        llmModel={llmConfig.model}
        llmConnected={llmConnected}
        dbName={databases.find(d => d.id === activeDbId)?.name || '未连接'}
        sessionTitle={sessions.find(s => s.id === activeSessionId)?.title}
      />
    </div>
  )
}
