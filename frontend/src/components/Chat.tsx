import { useState, useRef, useEffect } from 'react'
import type { Message, SchemaTable } from '../types'
import React from 'react'
import MessageBubble from './MessageBubble'

interface ChatProps {
  messages: Message[]
  isLoading: boolean
  onSend: (text: string) => void
  schema: SchemaTable[]
  mode: string
  onModeChange: (mode: string) => void
}

const EXAMPLE_QUESTIONS = [
  '有哪些数据表？',
  '给我看看数据概况',
  '帮我分析一下数据',
]

const Chat = React.memo(function Chat({ messages, isLoading, onSend, schema, mode, onModeChange }: ChatProps) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 自动调整输入框高度
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 120)}px`
    }
  }, [input])

  const handleSend = () => {
    if (!input.trim() || isLoading) return
    onSend(input.trim())
    setInput('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleExampleClick = (q: string) => {
    onSend(q)
  }

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-paper/30">
      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {messages.length === 0 ? (
          // 空状态
          <div className="h-full flex flex-col items-center justify-center text-center">
            <div className="text-4xl mb-4 opacity-20">📊</div>
            <h2 className="text-lg font-song text-ink-light mb-2">你好，我是你的数据分析助手</h2>
            <p className="text-sm text-ink-lighter font-kai mb-6 max-w-md">
              你可以直接问我关于数据的问题，我会查询数据库并回答你。
            </p>

            {/* 快捷示例问题 */}
            <div className="space-y-2">
              <p className="text-xs text-ink-lighter font-kai mb-3">试试这些问题：</p>
              {EXAMPLE_QUESTIONS.map((q, i) => (
                <button
                  key={i}
                  onClick={() => handleExampleClick(q)}
                  className="block w-full max-w-sm px-4 py-2 text-sm text-ink-light
                             bg-white/60 hover:bg-white hover:text-celadon-dark
                             ink-border rounded-sm transition-colors text-left"
                >
                  <span className="mr-2 text-celadon">→</span>
                  {q}
                </button>
              ))}
            </div>

            {/* 数据库表信息 */}
            {schema.length > 0 && (
              <div className="mt-8 text-center">
                <p className="text-xs text-ink-lighter font-kai mb-2">
                  已发现 {schema.length} 张数据表
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  {schema.map(t => (
                    <span
                      key={t.name}
                      className="px-2 py-0.5 text-xs text-ink-light bg-white/40 ink-border rounded-sm"
                    >
                      {t.name}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <>
            {messages.map(msg => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
          </>
        )}

        {/* 加载指示 */}
        {isLoading && (
          <div className="flex justify-start mb-4">
            <div className="bubble-agent">
              <div className="flex items-center gap-2 text-ink-lighter">
                <span className="w-2 h-2 bg-celadon rounded-full animate-pulse" />
                <span className="w-2 h-2 bg-celadon rounded-full animate-pulse" style={{ animationDelay: '0.2s' }} />
                <span className="w-2 h-2 bg-celadon rounded-full animate-pulse" style={{ animationDelay: '0.4s' }} />
                <span className="text-xs ml-1">正在分析…</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 */}
      <div className="flex-shrink-0 px-4 py-3 bg-white/60 ink-border border-b-0 border-x-0">
        <div className="flex items-end gap-2 max-w-4xl mx-auto">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入你的问题…"
            rows={1}
            className="flex-1 ink-input resize-none min-h-[56px] max-h-[200px] py-3 px-3 text-sm leading-relaxed"
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="btn-celadon flex items-center gap-1.5 h-[40px]"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
            发送
          </button>
        </div>
        {/* 模式切换 */}
        <div className="flex items-center justify-between mt-2 max-w-4xl mx-auto">
          <div className="flex items-center gap-2">
            <button
              onClick={() => onModeChange('fast')}
              className={`text-xs px-2 py-0.5 rounded-sm transition-colors ${
                mode === 'fast'
                  ? 'bg-celadon/20 text-celadon-dark font-medium'
                  : 'text-ink-lighter hover:text-ink'
              }`}
            >
              ⚡ 快速
            </button>
            <button
              onClick={() => onModeChange('quality')}
              className={`text-xs px-2 py-0.5 rounded-sm transition-colors ${
                mode === 'quality'
                  ? 'bg-celadon/20 text-celadon-dark font-medium'
                  : 'text-ink-lighter hover:text-ink'
              }`}
            >
              🎯 深度分析
            </button>
          </div>
          <span className="text-[10px] text-ink-lighter font-kai">Ctrl+Enter 发送</span>
        </div>
      </div>
    </div>
  )
})

export default Chat
