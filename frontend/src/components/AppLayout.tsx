import { useEffect, useCallback, useRef } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import StatusBar from './StatusBar'
import { api } from '../api'
import { useAuthStore } from '../store/authStore'
import { useConfigStore } from '../store/configStore'
import { useUIStore } from '../store/uiStore'
import { useSessionStore } from '../store/sessionStore'

/**
 * 应用布局组件
 * 作为路由的根布局，包含顶部导航栏、错误提示横幅、子路由内容出口和底部状态栏。
 * 负责初始化用户认证、加载数据库列表、加载配置信息以及定期检查 LLM 连接状态。
 */
export default function AppLayout() {
  // 使用选择器按需订阅 Store，避免不必要的重渲染
  const databases = useConfigStore(s => s.databases)
  const activeDbId = useConfigStore(s => s.activeDbId)
  const llmConnected = useConfigStore(s => s.llmConnected)
  const llmConfig = useConfigStore(s => s.llmConfig)
  const setDatabases = useConfigStore(s => s.setDatabases)
  const setLlmConnected = useConfigStore(s => s.setLlmConnected)
  const setLLMConfig = useConfigStore(s => s.setLLMConfig)
  const setSafetyConfig = useConfigStore(s => s.setSafetyConfig)
  const setSchema = useConfigStore(s => s.setSchema)

  const leftOpen = useUIStore(s => s.leftOpen)
  const error = useUIStore(s => s.error)
  const setLeftOpen = useUIStore(s => s.setLeftOpen)
  const setError = useUIStore(s => s.setError)

  const sessions = useSessionStore(s => s.sessions)
  const activeSessionId = useSessionStore(s => s.activeSessionId)

  const user = useAuthStore(s => s.user)
  const isInitialized = useAuthStore(s => s.isInitialized)
  const checkAuth = useAuthStore(s => s.checkAuth)
  const logout = useAuthStore(s => s.logout)
  const navigate = useNavigate()
  const location = useLocation()

  const errorTimerRef = useRef<ReturnType<typeof setTimeout>>()

  /**
   * 显示错误信息，5 秒后自动清除
   */
  const showError = useCallback((msg: string) => {
    setError(msg)
    clearTimeout(errorTimerRef.current)
    errorTimerRef.current = setTimeout(() => setError(null), 5000)
  }, [setError])

  /**
   * 检测 LLM 连接状态
   */
  const checkLLM = useCallback(async () => {
    try {
      const res = await api.testLLM()
      setLlmConnected(res.ok)
    } catch {
      setLlmConnected(false)
    }
  }, [setLlmConnected])

  /**
   * 加载数据库列表
   */
  const loadDatabases = useCallback(async () => {
    try {
      const data = await api.getDatabases()
      setDatabases(data.databases || [])
    } catch (err: any) {
      showError(`加载数据库列表失败: ${err.message || '未知错误'}`)
    }
  }, [setDatabases, showError])

  /**
   * 加载数据库 Schema
   */
  const loadSchema = useCallback(async () => {
    try {
      const data = await api.getSchema()
      setSchema(data.tables || [])
    } catch (err: any) {
      showError(`加载 Schema 失败: ${err.message || '未知错误'}`)
    }
  }, [setSchema, showError])

  /**
   * 加载 LLM 和安全配置
   */
  const loadConfig = useCallback(async () => {
    try {
      const data = await api.getConfig()
      if (data?.llm) setLLMConfig(prev => ({ ...prev, ...data.llm }))
      if (data?.safety) setSafetyConfig(prev => ({ ...prev, ...data.safety }))
    } catch (err: any) {
      showError(`加载配置失败: ${err.message || '未知错误'}`)
    }
  }, [setLLMConfig, setSafetyConfig, showError])

  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  useEffect(() => {
    if (!user) return
    loadSchema()
    loadDatabases()
    loadConfig()
    checkLLM()
  }, [user, loadSchema, loadDatabases, loadConfig, checkLLM])

  useEffect(() => {
    if (!user) return
    const timer = setInterval(checkLLM, 120000)
    return () => clearInterval(timer)
  }, [user, checkLLM])

  if (!isInitialized) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-paper-light">
        <p className="text-ink-lighter font-kai">加载中…</p>
      </div>
    )
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <header className="flex-shrink-0 flex items-center justify-between px-6 py-3 bg-white/80 backdrop-blur-sm ink-border border-t-0 border-x-0">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-song font-semibold text-ink tracking-wider">
            Data Chat
          </h1>
          <span className="text-xs text-ink-lighter font-kai">问你的数据</span>
        </div>
        <div className="flex items-center gap-4 text-ink-light">
          {user?.role === 'admin' && (
            <button
              onClick={() => navigate('/admin')}
              className={`p-1 rounded-sm transition-colors hover:bg-smoke ${location.pathname === '/admin' ? 'text-celadon' : ''}`}
              title="系统设置"
              aria-label="系统设置"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="3" />
                <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
              </svg>
            </button>
          )}
          <button
            onClick={() => navigate('/dashboard')}
            aria-label="切换看板"
            className={`p-1 rounded-sm transition-colors hover:bg-smoke ${location.pathname === '/dashboard' ? 'text-celadon' : ''}`}
            title="数据看板"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z" />
            </svg>
          </button>
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
          <div className="flex items-center gap-2 pl-2 border-l border-tea">
            <span className="text-xs text-ink-lighter font-kai">{user?.username}</span>
            {user?.role === 'admin' && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-sm bg-celadon/10 text-celadon-dark font-kai">管理员</span>
            )}
            <button
              onClick={logout}
              className="text-xs text-ink-lighter hover:text-cinnabar transition-colors font-kai"
            >
              退出
            </button>
          </div>
        </div>
      </header>

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

      <div className="flex-1 flex overflow-hidden">
        <Outlet />
      </div>

      <StatusBar
        llmModel={llmConfig.model}
        llmName={llmConfig.name}
        llmConnected={llmConnected}
        dbName={databases.find(d => d.id === activeDbId)?.name || '未连接'}
        sessionTitle={sessions.find(s => s.id === activeSessionId)?.title}
      />
    </div>
  )
}
