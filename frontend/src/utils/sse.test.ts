import { describe, it, expect, vi } from 'vitest'
import { parseSSEStream } from './sse'

function createMockReader(chunks: string[]): ReadableStreamDefaultReader<Uint8Array> {
  const encoder = new TextEncoder()
  let index = 0
  return {
    read: async () => {
      if (index < chunks.length) {
        const value = encoder.encode(chunks[index])
        index++
        return { done: false, value }
      }
      return { done: true, value: undefined as any }
    },
    releaseLock: vi.fn(),
    cancel: vi.fn() as any,
    closed: Promise.resolve(undefined),
  }
}

describe('parseSSEStream', () => {
  it('parses single SSE event from one chunk', async () => {
    const reader = createMockReader(['data: {"type":"thinking","content":"分析中"}\n\n'])
    const handler = vi.fn()
    await parseSSEStream(reader, handler)
    expect(handler).toHaveBeenCalledTimes(1)
    expect(handler).toHaveBeenCalledWith({ type: 'thinking', content: '分析中' })
  })

  it('parses multiple SSE events from one chunk', async () => {
    const reader = createMockReader([
      'data: {"type":"thinking"}\n\ndata: {"type":"plan"}\n\n',
    ])
    const handler = vi.fn()
    await parseSSEStream(reader, handler)
    expect(handler).toHaveBeenCalledTimes(2)
    expect(handler).toHaveBeenNthCalledWith(1, { type: 'thinking' })
    expect(handler).toHaveBeenNthCalledWith(2, { type: 'plan' })
  })

  it('handles events split across multiple chunks', async () => {
    const reader = createMockReader([
      'data: {"type":"thin',
      'king"}\n\n',
    ])
    const handler = vi.fn()
    await parseSSEStream(reader, handler)
    expect(handler).toHaveBeenCalledTimes(1)
    expect(handler).toHaveBeenCalledWith({ type: 'thinking' })
  })

  it('handles empty stream gracefully', async () => {
    const reader = createMockReader([])
    const handler = vi.fn()
    await parseSSEStream(reader, handler)
    expect(handler).not.toHaveBeenCalled()
  })

  it('handles events without data: prefix', async () => {
    const reader = createMockReader(['event: message\n\n'])
    const handler = vi.fn()
    await parseSSEStream(reader, handler)
    expect(handler).not.toHaveBeenCalled()
  })

  it('handles invalid JSON gracefully', async () => {
    const reader = createMockReader(['data: {invalid}\n\n'])
    const handler = vi.fn()
    await expect(parseSSEStream(reader, handler)).resolves.toBeUndefined()
    expect(handler).not.toHaveBeenCalled()
  })

  it('processes leftover buffer at end of stream', async () => {
    const reader = createMockReader([
      'data: {"type":"thinking"}\n\ndata: {"type":"',
    ])
    const handler = vi.fn()
    await parseSSEStream(reader, handler)
    expect(handler).toHaveBeenCalledTimes(1)
    expect(handler).toHaveBeenCalledWith({ type: 'thinking' })
  })
})
