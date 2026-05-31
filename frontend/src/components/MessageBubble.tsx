import React from 'react'
import type { Message } from '../types'
import MarkdownRenderer from './MarkdownRenderer'

interface MessageBubbleProps {
  message: Message
}

/**
 * 消息气泡组件
 * 处理不同类型的消息渲染（普通消息、进度消息、计划消息）
 */
const MessageBubble = React.memo(function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const [planOpen, setPlanOpen] = React.useState(false)
  const [sqlPopoverOpen, setSqlPopoverOpen] = React.useState(false)
  const hideTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)

  /**
   * 显示 SQL 弹出层
   */
  const showSqlPopover = React.useCallback(() => {
    if (hideTimerRef.current) {
      clearTimeout(hideTimerRef.current)
      hideTimerRef.current = null
    }
    setSqlPopoverOpen(true)
  }, [])

  /**
   * 隐藏 SQL 弹出层（延迟隐藏）
   */
  const hideSqlPopover = React.useCallback(() => {
    hideTimerRef.current = setTimeout(() => {
      setSqlPopoverOpen(false)
    }, 200)
  }, [])

  // 清理定时器
  React.useEffect(() => {
    return () => {
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current)
    }
  }, [])

  // 进度面板（quality 模式合并显示）
  if (message.isProgress) {
    const steps = message.progressSteps || []
    const done = steps.filter(s => s.status === 'done').length
    const total = steps.length
    return (
      <div className="flex justify-start mb-4">
        <div className="bubble-agent max-w-lg w-full">
          <div className="flex items-center gap-1.5 mb-2">
            <span className="text-xs text-celadon-dark font-kai">📋 {message.progressTitle || '分析进度'}</span>
            <span className="text-[10px] text-ink-lighter ml-auto">{done}/{total}</span>
          </div>
          <div className="space-y-1">
            {steps.map((step, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <span className="shrink-0 mt-0.5">
                  {step.status === 'done' ? (
                    <span className="text-celadon-dark">✅</span>
                  ) : step.status === 'running' ? (
                    <span className="inline-block w-3.5 h-3.5 border-2 border-celadon border-t-transparent rounded-full animate-spin" />
                  ) : step.status === 'error' ? (
                    <span className="text-cinnabar">❌</span>
                  ) : (
                    <span className="text-ink-lighter/40">⏳</span>
                  )}
                </span>
                <div className="flex-1 min-w-0">
                  <div className={`text-xs ${step.status === 'done' ? 'text-ink' : step.status === 'running' ? 'text-celadon-dark font-medium' : 'text-ink-lighter'}`}>
                    {step.label}
                  </div>
                  {step.detail && step.status === 'running' && (
                    <div className="text-[10px] text-ink-lighter mt-0.5 truncate">{step.detail}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
          {done < total && (
            <div className="mt-2 text-[10px] text-ink-lighter font-kai animate-pulse">
              正在执行…
            </div>
          )}
        </div>
      </div>
    )
  }

  // 可折叠的分析计划
  if (message.isPlan) {
    return (
      <div className="flex justify-start mb-4">
        <div className="bubble-agent max-w-lg w-full">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-xs text-celadon-dark font-kai">📋 分析计划</span>
          </div>
          <div
            className="text-xs text-ink-lighter font-kai cursor-pointer flex items-center gap-1 select-none"
            onClick={() => setPlanOpen(!planOpen)}
          >
            {planOpen ? '▼ 收起' : '▶ 点击展开'}
          </div>
          {planOpen && (
            <div className="mt-2 text-sm leading-relaxed text-ink">
              <MarkdownRenderer 
                content={message.planContent || ''} 
                queryResults={message.query_results}
              />
            </div>
          )}
        </div>
      </div>
    )
  }

  const hasQueries = !isUser && ((message.query_results && message.query_results.length > 0) || (message.sql_queries && message.sql_queries.length > 0))
  const queries = !isUser && message.query_results && message.query_results.length > 0
    ? message.query_results.map(q => ({ qn: q.qn, sql: q.sql, ok: q.ok, error: q.error }))
    : (message.sql_queries || []).map((sql, i) => ({ qn: i + 1, sql, ok: true as const, error: undefined }))

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={isUser ? 'bubble-user' : 'bubble-agent'}>
        {!isUser && (
          <div className="text-xs text-ink-lighter font-kai mb-1 flex items-center gap-1">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2a4 4 0 1 0 0 8 4 4 0 0 0 0-8z" />
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            </svg>
            Data Chat
          </div>
        )}

        <div className={`text-sm leading-relaxed ${isUser ? 'text-white' : 'text-ink'}`}>
          {isUser ? (
            message.content
          ) : (
            <MarkdownRenderer 
              content={message.content} 
              queryResults={message.query_results}
            />
          )}
        </div>

        {message.tool_calls && message.tool_calls.length > 0 && (
          <div className={`mt-2 text-xs ${isUser ? 'text-white/60' : 'text-ink-lighter'} font-kai`}>
            🔍 查询了数据库
          </div>
        )}

        {hasQueries && (
          <div
            className="mt-2 flex justify-end relative"
            onMouseEnter={showSqlPopover}
            onMouseLeave={hideSqlPopover}
          >
            <div className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-smoke text-ink-lighter hover:text-ink hover:bg-paper/60 transition-colors cursor-default">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <ellipse cx="12" cy="5" rx="8" ry="3" />
                <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5" />
                <path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />
              </svg>
            </div>
            {sqlPopoverOpen && (
              <div
                className="absolute right-0 bottom-full mb-1 w-[480px] max-w-[85vw] bg-white ink-border rounded-lg shadow-lg overflow-hidden z-50"
                onMouseEnter={showSqlPopover}
                onMouseLeave={hideSqlPopover}
              >
                <div className="px-3 py-2 text-xs text-ink-lighter font-kai border-b border-ink-lighter/10">
                  使用的查询语句
                </div>
                <div className="max-h-72 overflow-y-auto">
                  {queries.map(q => (
                    <div key={q.qn} className="px-3 py-2 border-b border-ink-lighter/10 last:border-b-0">
                      <div className="flex items-center gap-2 text-[10px] text-ink-lighter mb-1">
                        <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-celadon/20 text-celadon-dark text-[10px] font-bold leading-none">
                          {q.qn}
                        </span>
                        <span className="font-kai">{q.ok ? '成功' : '失败'}</span>
                      </div>
                      <pre className="text-[10px] font-mono text-ink whitespace-pre-wrap break-words">{q.sql}</pre>
                      {!q.ok && q.error && (
                        <div className="mt-1 text-[10px] text-cinnabar font-kai whitespace-pre-wrap break-words">{q.error}</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
})

export default MessageBubble
