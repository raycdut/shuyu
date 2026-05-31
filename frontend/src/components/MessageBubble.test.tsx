import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import type { Message } from '../types'
import MessageBubble from './MessageBubble'

function msg(overrides: Partial<Message> = {}): Message {
  return { id: 'test-1', role: 'user', content: '', ...overrides } as Message
}

describe('MessageBubble', () => {
  it('renders user message right-aligned', () => {
    const { container } = render(<MessageBubble message={msg({ content: '你好' })} />)
    expect(screen.getByText('你好')).toBeInTheDocument()
    const outer = container.firstElementChild
    expect(outer?.className).toContain('justify-end')
  })

  it('renders assistant message left-aligned', () => {
    const { container } = render(<MessageBubble message={msg({ role: 'assistant', content: '我是助手' })} />)
    expect(screen.getByText('我是助手')).toBeInTheDocument()
    const outer = container.firstElementChild
    expect(outer?.className).toContain('justify-start')
  })

  it('shows agent name for assistant messages', () => {
    render(<MessageBubble message={msg({ role: 'assistant', content: '回答' })} />)
    expect(screen.getByText('数语')).toBeInTheDocument()
  })

  it('renders markdown table', () => {
    const text = '| 产品 | 价格 |\n| --- | --- |\n| 苹果 | 5.0 |\n| 香蕉 | 3.5 |'
    render(<MessageBubble message={msg({ role: 'assistant', content: text })} />)
    expect(screen.getByText('产品')).toBeInTheDocument()
    expect(screen.getByText('价格')).toBeInTheDocument()
    expect(screen.getByText('苹果')).toBeInTheDocument()
    expect(screen.getByText('香蕉')).toBeInTheDocument()
  })

  it('shows tool call indicator', () => {
    const toolCallMsg = msg({
      role: 'assistant',
      content: '查到了',
      tool_calls: [{ id: 'c1', type: 'function', function: { name: 'query', arguments: '{}' } }],
    })
    render(<MessageBubble message={toolCallMsg} />)
    expect(screen.getByText('🔍 查询了数据库')).toBeInTheDocument()
  })

  it('renders regular text without markdown table', () => {
    render(<MessageBubble message={msg({ role: 'assistant', content: '这是一段普通文本。\n没有表格。' })} />)
    expect(screen.getByText(/这是一段普通文本/)).toBeInTheDocument()
  })
})
