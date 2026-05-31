import { useCallback } from 'react'
import { useSessionStore } from '../store/sessionStore'
import { useConfigStore } from '../store/configStore'
import { api } from '../api'
import { Message, nextMsgId, ProgressStep } from '../types'
import { useSessions } from './useSessions'

/**
 * 聊天流 Hook
 * 负责 SSE 连接、缓冲区处理和进度状态更新
 */
export function useChatStream() {
  const activeSessionId = useSessionStore(s => s.activeSessionId)
  const isLoading = useSessionStore(s => s.isLoading)
  const setIsLoading = useSessionStore(s => s.setIsLoading)
  const setMessages = useSessionStore(s => s.setMessages)
  const setActiveSessionId = useSessionStore(s => s.setActiveSessionId)

  const activeDbId = useConfigStore(s => s.activeDbId)
  const mode = useConfigStore(s => s.mode)

  const { loadSessions } = useSessions()

  /**
   * 发送消息
   */
  const handleSendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return

    const userMsg: Message = { id: nextMsgId(), role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])

    if (!activeDbId) {
      const warnMsg: Message = {
        id: nextMsgId(),
        role: 'assistant',
        content: '⚠️ 请先在左侧选择一个数据库，然后再提问。',
      }
      setMessages(prev => [...prev, warnMsg])
      return
    }

    setIsLoading(true)

    try {
      if (mode === 'quality') {
        // 1. 立即初始化进度消息
        const progressId = nextMsgId()
        let progressSteps: ProgressStep[] = [
          { label: '生成分析计划', status: 'pending' },
          { label: '审核分析计划', status: 'pending' },
          { label: '执行查询', status: 'pending' },
          { label: '生成分析报告', status: 'pending' },
        ]

        setMessages(prev => [...prev, {
          id: progressId,
          role: 'assistant',
          content: '',
          isProgress: true,
          progressSteps: [...progressSteps],
          progressTitle: '准备分析中...',
        }])

        const updateProgress = (title?: string) => {
          setMessages(prev => prev.map(m =>
            // 只有当消息仍然是进度状态时才更新，防止 late events 覆盖最终结果
            (m.id === progressId && m.isProgress)
              ? { 
                  ...m, 
                  progressSteps: progressSteps.map(s => ({ ...s })), // 确保对象引用也更新
                  progressTitle: title || m.progressTitle,
                } 
              : m
          ))
        }

        // 2. 发起请求
        console.log('[Chat] 发起深度分析请求...', { text, activeSessionId, activeDbId })
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

        if (!resp.ok) {
          const errorText = await resp.text()
          console.error('[Chat] 请求失败', resp.status, errorText)
          throw new Error(errorText || `HTTP ${resp.status}`)
        }

        if (!resp.body) throw new Error('ReadableStream not supported')
        
        const reader = resp.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let sqlCount = 0

        console.log('[Chat] SSE 连接已建立，开始解析数据流...')

        const handleEvent = (event: any) => {
          console.log(`[SSE Event] ${event.type}`, event)

          if (event.type === 'thinking') {
            updateProgress(event.content || '正在分析问题...')
          } else if (event.type === 'plan') {
            progressSteps[0].status = 'done'
            progressSteps[1].status = 'running'
            updateProgress('正在审核分析计划')
          } else if (event.type === 'plan_reflect') {
            if (event.content?.includes('通过')) {
              progressSteps[1].status = 'done'
              progressSteps[2].status = 'running'
              updateProgress('正在执行数据查询')
            } else {
              updateProgress(`计划审核: ${event.content?.slice(0, 20)}...`)
            }
          } else if (event.type === 'query') {
            sqlCount++
            progressSteps[2].status = 'running'
            progressSteps[2].detail = `📊 正在执行查询 ${sqlCount}`
            updateProgress()
          } else if (event.type === 'step') {
            if (event.step && event.total) {
              progressSteps[2].label = `执行查询（第 ${event.step}/${event.total} 步）`
            }
            updateProgress()
          } else if (event.type === 'summarize') {
            progressSteps[2].status = 'done'
            progressSteps[3].status = 'running'
            updateProgress('正在生成分析报告')
          } else if (event.type === 'session_id') {
            console.log(`[Chat] 收到 Session ID: ${event.session_id}`)
            setActiveSessionId(event.session_id)
          } else if (event.type === 'done') {
            console.log('[Chat] 收到 Done 事件，更新最终消息')
            progressSteps[3].status = 'done'
            setMessages(prev => prev.map(m =>
              m.id === progressId
                ? { 
                    ...m,
                    isProgress: false, 
                    role: 'assistant', 
                    content: event.content || '分析完成。', 
                    sql_queries: event.sql_queries || [], 
                    query_results: event.query_results || [],
                    progressSteps: progressSteps.map(s => ({ ...s }))
                  }
                : m
            ))
          } else if (event.type === 'error') {
            console.error('[Chat] SSE 收到错误事件', event)
            throw new Error(event.content || '分析过程中发生错误')
          }
        }

        // 3. 循环处理 SSE 流
        while (true) {
          const { done, value } = await reader.read()

          if (value) {
            buffer += decoder.decode(value, { stream: true })
          } else if (done) {
            buffer += decoder.decode() // flush
          }

          // 处理缓冲区中所有完整的 SSE 事件 (\n\n 分隔)
          while (buffer.indexOf('\n\n') !== -1) {
            const eventEndIndex = buffer.indexOf('\n\n')
            const completeEvent = buffer.substring(0, eventEndIndex)
            buffer = buffer.substring(eventEndIndex + 2)

            const lines = completeEvent.split('\n')
            let eventData = ''
            
            for (const line of lines) {
              const trimmed = line.trim()
              if (trimmed.startsWith('data: ')) {
                eventData += trimmed.slice(6)
              }
            }

            if (eventData) {
              try {
                const event = JSON.parse(eventData)
                handleEvent(event)
              } catch (e) {
                console.error('[Chat] SSE 事件解析失败', e, eventData)
              }
            }
          }

          if (done) {
            console.log('[Chat] SSE 流读取完成')
            
            // 处理流结束但缓冲区中可能剩下的最后一段（通常 SSE 以 \n\n 结尾，但做个保险）
            if (buffer.trim().startsWith('data: ')) {
              const eventData = buffer.trim().slice(6)
              try {
                const event = JSON.parse(eventData)
                handleEvent(event)
              } catch (e) {
                console.error('[Chat] 剩余 buffer 解析失败', e, buffer)
              }
            }
            break
          }
        }
      } else {
        // 快速模式
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
      await loadSessions()
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
  }, [activeSessionId, activeDbId, isLoading, mode, setIsLoading, setMessages, setActiveSessionId, loadSessions])

  return { handleSendMessage }
}
