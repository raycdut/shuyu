import { useState, useEffect, useCallback, useRef } from 'react'
import Sidebar from './components/Sidebar'
import Chat from './components/Chat'
import ConfigPanel from './components/ConfigPanel'
import StatusBar from './components/StatusBar'
import { Session, DatabaseInfo, LLMConfig, SafetyConfig, Message, nextMsgId } from './types'
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
  const [mode, setMode] = useState('fast')
  const [schema, setSchema] = useState<{ name: string; columns: { name: string; type: string }[] }[]>([])

  // LLM 连接状态
  const [llmConnected, setLlmConnected] = useState<boolean | null>(null)

  // 配置
  const [llmConfig, setLLMConfig] = useState<LLMConfig>({
    provider: 'openai',
    model: 'gpt-4o',
    api_key: '',
    api_base: '',
    timeout: 60,
  })
  const [safetyConfig, setSafetyConfig] = useState<SafetyConfig>({
    read_only: true,
    require_approval: true,
    max_rows: 1000,
  })

  // 面板展开
  const [leftOpen, setLeftOpen] = useState(true)
  const [rightOpen, setRightOpen] = useState(true)

  // 全局错误状态
  const [error, setError] = useState<string | null>(null)
  const errorTimerRef = useRef<ReturnType<typeof setTimeout>>()

  const showError = useCallback((msg: string) => {
    setError(msg)
    clearTimeout(errorTimerRef.current)
    errorTimerRef.current = setTimeout(() => setError(null), 5000)
  }, [])

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
    } catch (err: any) {
      showError(`加载会话失败: ${err.message || '未知错误'}`)
    }
  }

  const loadSchema = async () => {
    try {
      const data = await api.getSchema()
      setSchema(data.tables || [])
    } catch (err: any) {
      showError(`加载 Schema 失败: ${err.message || '未知错误'}`)
    }
  }

  const loadDatabases = async () => {
    try {
      const data = await api.getDatabases()
      setDatabases(data.databases || [])
    } catch (err: any) {
      showError(`加载数据库列表失败: ${err.message || '未知错误'}`)
    }
  }

  const loadConfig = async () => {
    try {
      const data = await api.getConfig()
      if (data?.llm) setLLMConfig(prev => ({ ...prev, ...data.llm }))
      if (data?.safety) setSafetyConfig(prev => ({ ...prev, ...data.safety }))
    } catch (err: any) {
      showError(`加载配置失败: ${err.message || '未知错误'}`)
    }
  }

  // --- 对话 ---
  const handleSendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return

    const userMsg: Message = { id: nextMsgId(), role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setIsLoading(true)

    try {
      if (mode === 'quality') {
        if (!activeDbId) {
          const warnMsg: Message = {
            id: nextMsgId(),
            role: 'assistant',
            content: '⚠️ 请先在左侧选择一个数据库，然后再提问。',
          }
          setMessages(prev => [...prev, warnMsg])
          return
        }
        // 深度分析模式：合并为一个进度面板
        const resp = await fetch('/api/chat/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: text,
            session_id: activeSessionId || null,
            db_id: activeDbId || null,
            mode: 'quality'
          }),
        })
        const reader = resp.body!.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        // 进度步骤外部管理（避免闭包陈旧引用）
        let planReflected = false
        let executionDone = false
        let progressSteps: { label: string; status: 'pending' | 'running' | 'done' | 'error'; detail?: string }[] = [
          { label: '生成分析计划', status: 'running' },
          { label: '审核分析计划', status: 'pending' },
          { label: '执行查询', status: 'pending' },
          { label: '生成分析报告', status: 'pending' },
        ]

        // 创建进度消息
        const progressId = nextMsgId()
        setMessages(prev => [...prev, {
          id: progressId,
          role: 'assistant',
          content: '',
          isProgress: true,
          progressSteps: [...progressSteps],
          progressTitle: '深度分析中',
        }])

        const updateProgress = () => {
          setMessages(prev => prev.map(m =>
            m.id === progressId ? { ...m, progressSteps: [...progressSteps], isProgress: true } : m
          ))
        }

        let sqlCount = 0
        let allSqlQueries: string[] = []
        let allQueryResults: any[] = []

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })

          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            try {
              const event = JSON.parse(line.slice(6))
              console.log('[SSE]', event.type, (event.content || '').slice(0, 60))

              if (event.type === 'plan') {
                // Plan ready — plan step done, reflect starts
                progressSteps[0].status = 'done'
                progressSteps[1].status = 'running'
                updateProgress()
              } else if (event.type === 'plan_reflect') {
                if (event.content?.includes('通过')) {
                  progressSteps[1].status = 'done'
                  progressSteps[2].status = 'running'
                  planReflected = true
                  updateProgress()
                }
              } else if (event.type === 'query') {
                sqlCount++
                progressSteps[2].detail = `📊 查询 ${sqlCount}`
              } else if (event.type === 'step') {
                if (event.step && event.total) {
                  progressSteps[2].label = `执行查询（第 ${event.step}/${event.total} 步）`
                }
                updateProgress()
              } else if (event.type === 'step_done') {
                // step completed — keep running
              } else if (event.type === 'summarize') {
                progressSteps[2].status = 'done'
                progressSteps[3].status = 'running'
                executionDone = true
                updateProgress()
              } else if (event.type === 'session_id') {
                setActiveSessionId(event.session_id)
              } else if (event.type === 'thinking') {
                // skip
              } else if (event.type === 'done') {
                allSqlQueries = event.sql_queries || []
                allQueryResults = event.query_results || []
                // Replace progress message with final answer
                setMessages(prev => prev.map(m =>
                  m.id === progressId
                    ? { id: progressId, role: 'assistant', content: event.content, sql_queries: allSqlQueries, query_results: allQueryResults }
                    : m
                ))
              }
            } catch { /* skip */ }
          }
        }
      } else {
        // 快速模式：原有逻辑
        const res = await api.sendMessage(text, activeSessionId ?? undefined, activeDbId ?? undefined, mode)
        setActiveSessionId(res.session_id)

        const agentMsg: Message = {
          id: nextMsgId(),
          role: 'assistant',
          content: res.reply,
          tool_calls: res.tool_calls,
          sql_queries: res.sql_queries,
          query_results: res.query_results,
        }
        setMessages(prev => [...prev, agentMsg])
      }
      loadSessions()
    } catch (err: any) {
      const errorMsg: Message = {
        id: nextMsgId(),
        role: 'assistant',
        content: `抱歉，请求失败：${err.message || '未知错误'}`,
      }
      setMessages(prev => [...prev, errorMsg])
    } finally {
      setIsLoading(false)
    }
  }, [activeSessionId, activeDbId, isLoading, mode])

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
    } catch (err: any) {
      showError(`重命名失败: ${err.message || '未知错误'}`)
    }
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
    } catch (err: any) {
      showError(`删除会话失败: ${err.message || '未知错误'}`)
    }
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
            aria-label="切换侧栏"
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
            aria-label="切换配置面板"
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

      {/* ===== 错误提示 Toast ===== */}
      {error && (
        <div className="flex-shrink-0 flex items-center justify-between px-4 py-2 bg-cinnabar/10 text-cinnabar text-sm border-b border-cinnabar/20">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-4 p-0.5 hover:bg-cinnabar/10 rounded-sm" aria-label="关闭错误提示">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      )}

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
          onClearAllSessions={async () => {
            handleNewSession()
            try {
              const res = await fetch('/api/sessions/clear', { method: 'POST' })
              if (!res.ok) throw new Error(`HTTP ${res.status}`)
              loadSessions()
            } catch (err: any) {
              showError(`清空会话失败: ${err.message || '未知错误'}`)
              loadSessions()
            }
          }}
        />

        {/* 分隔线 */}
        {leftOpen && <div className="w-px bg-tea flex-shrink-0" />}

        {/* 中栏 — 聊天 */}
              <Chat
                messages={messages}
                isLoading={isLoading}
                onSend={handleSendMessage}
                schema={schema}
                mode={mode}
                onModeChange={setMode}
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
