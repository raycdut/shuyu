import type { Message } from '../types'

interface MessageBubbleProps {
  message: Message
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  // 检查是否包含表格数据（由查询结果渲染）
  const content = renderContent(message.content)

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={isUser ? 'bubble-user' : 'bubble-agent'}>
        {/* 角色标识 */}
        {!isUser && (
          <div className="text-xs text-ink-lighter font-kai mb-1 flex items-center gap-1">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2a4 4 0 1 0 0 8 4 4 0 0 0 0-8z" />
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            </svg>
            Data Chat
          </div>
        )}

        {/* 内容 */}
        <div className={`text-sm leading-relaxed whitespace-pre-wrap ${isUser ? 'text-white' : 'text-ink'}`}>
          {content}
        </div>

        {/* 工具调用信息 */}
        {message.tool_calls && message.tool_calls.length > 0 && (
          <div className={`mt-2 text-xs ${isUser ? 'text-white/60' : 'text-ink-lighter'} font-kai`}>
            🔍 查询了数据库
          </div>
        )}
      </div>
    </div>
  )
}

/** 渲染消息内容：检测并渲染 Markdown 表格 */
function renderContent(text: string) {
  // 尝试解析表格行
  const lines = text.split('\n')
  const elements: JSX.Element[] = []
  let inTable = false
  let tableRows: string[][] = []
  let tableHeaders: string[] = []

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // 检测表格行：| 内容 | 内容 |
    const tableMatch = line.match(/^\|(.+)\|$/)
    if (tableMatch) {
      const cells = tableMatch[1].split('|').map(c => c.trim())

      if (!inTable) {
        inTable = true
        tableHeaders = cells
        tableRows = []
        continue
      }

      // 分隔行 | --- | --- |
      if (cells.every(c => /^[-:]+$/.test(c))) continue

      tableRows.push(cells)
      continue
    }

    // 表格结束
    if (inTable) {
      elements.push(renderTable(tableHeaders, tableRows))
      inTable = false
      tableHeaders = []
      tableRows = []
    }

    elements.push(<span key={i}>{line}<br /></span>)
  }

  // 末尾可能还有未关闭的表格
  if (inTable) {
    elements.push(renderTable(tableHeaders, tableRows))
  }

  return elements.length > 0 ? elements : text
}

function renderTable(headers: string[], rows: string[][]) {
  return (
    <table key={`table-${Math.random()}`} className="query-table">
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
