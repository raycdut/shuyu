import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import StatusBar from './StatusBar'

describe('StatusBar', () => {
  it('shows model name', () => {
    render(<StatusBar llmModel="deepseek-v4-flash" llmConnected={null} dbName="测试库" />)
    expect(screen.getByText('deepseek-v4-flash')).toBeInTheDocument()
  })

  it('shows database name', () => {
    render(<StatusBar llmModel="gpt-4o" llmConnected={null} dbName="零售DB" />)
    expect(screen.getByText('零售DB')).toBeInTheDocument()
  })

  it('shows session title when provided', () => {
    render(<StatusBar llmModel="gpt-4o" llmConnected={null} dbName="db" sessionTitle="本月分析" />)
    expect(screen.getByText('本月分析')).toBeInTheDocument()
  })

  it('shows green dot title when connected', () => {
    render(<StatusBar llmModel="gpt-4o" llmConnected={true} dbName="db" />)
    expect(screen.getByTitle('已连接')).toBeInTheDocument()
  })

  it('shows gray dot title when not connected', () => {
    render(<StatusBar llmModel="gpt-4o" llmConnected={false} dbName="db" />)
    expect(screen.getByTitle('未连接')).toBeInTheDocument()
  })

  it('shows checking title when testing', () => {
    render(<StatusBar llmModel="gpt-4o" llmConnected={null} dbName="db" />)
    expect(screen.getByTitle('检测中…')).toBeInTheDocument()
  })

  it('does not render session section when title is empty', () => {
    const { container } = render(<StatusBar llmModel="gpt-4o" llmConnected={null} dbName="db" />)
    // The session title SVG + text should not be present
    expect(container.querySelector('footer')?.children[0]?.children.length ?? 0).toBe(0)
  })
})
