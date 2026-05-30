import React from 'react'
import type { Message } from '../types'

interface MessageBubbleProps {
  message: Message
}

const MessageBubble = React.memo(function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const content = renderContent(message.content)

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
          {content}
        </div>

        {message.tool_calls && message.tool_calls.length > 0 && (
          <div className={`mt-2 text-xs ${isUser ? 'text-white/60' : 'text-ink-lighter'} font-kai`}>
            🔍 查询了数据库
          </div>
        )}

        {/* 显示 SQL 查询来源 */}
        {!isUser && message.sql_queries && message.sql_queries.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {message.sql_queries.map((sql, i) => (
              <span key={i} className="text-[10px] bg-smoke text-ink-lighter px-1.5 py-0.5 rounded font-mono"
                title={sql}>
                📋 查询 {i + 1}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
})

export default MessageBubble

/** 渲染消息内容：Markdown 表格 + 基本 Markdown 格式 */
function renderContent(text: string) {
  const lines = text.split('\n')
  const elements: JSX.Element[] = []
  let inTable = false
  let tableRows: string[][] = []
  let tableHeaders: string[] = []
  let inCodeBlock = false
  let codeBuffer: string[] = []

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // 代码块 ```
    if (line.trimStart().startsWith('```')) {
      if (inCodeBlock) {
        elements.push(renderCodeBlock(codeBuffer.join('\n')))
        codeBuffer = []
        inCodeBlock = false
      } else {
        inCodeBlock = true
      }
      continue
    }

    if (inCodeBlock) {
      codeBuffer.push(line)
      continue
    }

    // 检测表格行
    const tableMatch = line.match(/^\|(.+)\|$/)
    if (tableMatch) {
      const cells = tableMatch[1].split('|').map(c => c.trim())
      if (!inTable) {
        inTable = true
        tableHeaders = cells
        tableRows = []
        continue
      }
      if (cells.every(c => /^[-:]+$/.test(c))) continue
      tableRows.push(cells)
      continue
    }

    if (inTable) {
      elements.push(renderTable(tableHeaders, tableRows))
      inTable = false
      tableHeaders = []
      tableRows = []
    }

    elements.push(renderTextLine(line, i))
  }

  if (inTable) elements.push(renderTable(tableHeaders, tableRows))
  if (inCodeBlock) elements.push(renderCodeBlock(codeBuffer.join('\n')))

  return elements.length > 0 ? elements : text
}

/** 渲染一行文本中的 Markdown 语法 */
function renderTextLine(line: string, key: number): JSX.Element {
  if (!line.trim()) return <br key={key} />

  // 检测引用 > xxx
  const quoteMatch = line.match(/^>\s?(.*)/)
  if (quoteMatch) {
    return (
      <div key={key} className="border-l-2 border-celadon/40 pl-3 py-0.5 my-1 text-ink-light italic">
        {renderInline(quoteMatch[1])}
      </div>
    )
  }

  // 检测分隔线 ---
  if (/^---+\s*$/.test(line)) {
    return <hr key={key} className="my-2 border-ink-lighter/20" />
  }

  // 检测有序列表 1. xxx
  const olMatch = line.match(/^(\s*)(\d+)\.\s+(.*)/)
  if (olMatch) {
    return (
      <div key={key} className="flex gap-2 ml-4 mb-0.5">
        <span className="text-ink-lighter shrink-0">{olMatch[2]}.</span>
        <span>{renderInline(olMatch[3])}</span>
      </div>
    )
  }

  // 检测无序列表 - xxx
  const ulMatch = line.match(/^(\s*)[*-]\s+(.*)/)
  if (ulMatch) {
    return (
      <div key={key} className="flex gap-2 ml-4 mb-0.5">
        <span className="text-ink-lighter shrink-0">·</span>
        <span>{renderInline(ulMatch[2])}</span>
      </div>
    )
  }

  // 检测标题 ### xxx
  const hMatch = line.match(/^(#{1,6})\s+(.*)/)
  if (hMatch) {
    const level = hMatch[1].length
    const sizes = ['text-lg font-bold', 'text-base font-semibold', 'text-sm font-semibold', 'text-sm font-medium', 'text-xs font-medium', 'text-xs']
    return <div key={key} className={`${sizes[level - 1] || 'text-sm font-medium'} mb-1 mt-1`}>{renderInline(hMatch[2])}</div>
  }

  // 普通文本
  return <div key={key} className="mb-0.5">{renderInline(line)}</div>
}

/** 渲染行内 Markdown：加粗、斜体、行内代码、查询标记 */
function renderInline(text: string): JSX.Element[] {
  const parts: JSX.Element[] = []
  let remaining = text
  let idx = 0

  while (remaining.length > 0) {
    // 查询标记 [Q1] [Q2]
    const qMatch = remaining.match(/\[Q(\d+)\]/)
    if (qMatch && qMatch.index !== undefined) {
      if (qMatch.index > 0) parts.push(<span key={idx++}>{qMatch.input?.slice(0, qMatch.index)}</span>)
      parts.push(
        <span key={idx++} className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-celadon/20 text-celadon-dark text-[10px] font-bold leading-none">
          {qMatch[1]}
        </span>
      )
      remaining = remaining.slice((qMatch.index || 0) + qMatch[0].length)
      continue
    }
    // 行内代码 `code`
    const codeMatch = remaining.match(/`([^`]+)`/)
    if (codeMatch && codeMatch.index !== undefined) {
      if (codeMatch.index > 0) parts.push(<span key={idx++}>{codeMatch.input?.slice(0, codeMatch.index)}</span>)
      parts.push(<code key={idx++} className="bg-smoke text-celadon-dark px-1 py-0.5 rounded text-[0.8em] font-mono">{codeMatch[1]}</code>)
      remaining = remaining.slice((codeMatch.index || 0) + codeMatch[0].length)
      continue
    }

    // 加粗 **text**
    const boldMatch = remaining.match(/\*\*(.+?)\*\*/)
    if (boldMatch && boldMatch.index !== undefined) {
      if (boldMatch.index > 0) parts.push(<span key={idx++}>{boldMatch.input?.slice(0, boldMatch.index)}</span>)
      parts.push(<strong key={idx++} className="font-semibold">{boldMatch[1]}</strong>)
      remaining = remaining.slice((boldMatch.index || 0) + boldMatch[0].length)
      continue
    }

    // 斜体 *text*
    const italicMatch = remaining.match(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/)
    if (italicMatch && italicMatch.index !== undefined) {
      if (italicMatch.index > 0) parts.push(<span key={idx++}>{italicMatch.input?.slice(0, italicMatch.index)}</span>)
      parts.push(<em key={idx++}>{italicMatch[1]}</em>)
      remaining = remaining.slice((italicMatch.index || 0) + italicMatch[0].length)
      continue
    }

    parts.push(<span key={idx++}>{remaining}</span>)
    break
  }

  return parts
}

function renderTable(headers: string[], rows: string[][]) {
  return (
    <table key={`table-${Math.random()}`} className="query-table my-2">
      <thead>
        <tr>
          {headers.map((h, i) => <th key={i}>{h}</th>)}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, ri) => (
          <tr key={ri}>
            {row.map((cell, ci) => <td key={ci}>{cell}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function renderCodeBlock(code: string) {
  return (
    <pre key={`code-${Math.random()}`} className="bg-smoke rounded-lg p-3 my-2 overflow-x-auto text-xs font-mono leading-relaxed">
      <code>{code}</code>
    </pre>
  )
}
