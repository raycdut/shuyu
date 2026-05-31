/**
 * SSE 流解析工具
 * 从 ReadableStream 中逐块读取、缓冲并解析 Server-Sent Events
 */

export interface SSEEvent {
  type: string
  [key: string]: any
}

export type SSEEventHandler = (event: SSEEvent) => void

/**
 * 从 ReadableStreamDefaultReader 中读取并解析 SSE 流
 * 按 \n\n 分隔事件，从 data: 前缀提取 JSON 负载
 */
export async function parseSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  onEvent: SSEEventHandler,
): Promise<void> {
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()

    if (value) {
      buffer += decoder.decode(value, { stream: true })
    } else if (done) {
      buffer += decoder.decode()
    }

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
          onEvent(event)
        } catch (e) {
          console.error('[SSE] 事件解析失败', e, eventData)
        }
      }
    }

    if (done) {
      if (buffer.trim().startsWith('data: ')) {
        const eventData = buffer.trim().slice(6)
        try {
          const event = JSON.parse(eventData)
          onEvent(event)
        } catch (e) {
          console.error('[SSE] 剩余 buffer 解析失败', e, buffer)
        }
      }
      break
    }
  }
}
