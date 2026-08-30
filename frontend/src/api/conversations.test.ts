import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ConversationStreamEvent } from '../types/conversation'
import { streamMessage } from './conversations'


function streamResponse(chunks: string[]): Response {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk))
      }
      controller.close()
    },
  })

  return new Response(body, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('streamMessage', () => {
  it('parses SSE events split across arbitrary network chunks', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        streamResponse([
          'event: token\ndata: {"content":"你',
          '好"}\n\nevent: token\ndata: {"content":"！"}\n',
          '\n',
        ]),
      ),
    )
    const events: ConversationStreamEvent[] = []

    await streamMessage(
      'knowledge-base-id',
      'conversation-id',
      { content: '测试问题' },
      (event) => events.push(event),
    )

    expect(events).toEqual([
      { event: 'token', data: { content: '你好' } },
      { event: 'token', data: { content: '！' } },
    ])
  })

  it('throws ApiError for a failed HTTP response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: '会话不存在' }), {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )

    await expect(
      streamMessage('kb', 'conversation', { content: '问题' }, vi.fn()),
    ).rejects.toMatchObject({
      name: 'ApiError',
      message: '会话不存在',
      status: 404,
    })
  })

  it('reports an error event and rejects the stream', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        streamResponse([
          'event: error\ndata: {"detail":"模型服务不可用"}\n\n',
        ]),
      ),
    )
    const onEvent = vi.fn()

    await expect(
      streamMessage('kb', 'conversation', { content: '问题' }, onEvent),
    ).rejects.toThrow('模型服务不可用')
    expect(onEvent).toHaveBeenCalledWith({
      event: 'error',
      data: { detail: '模型服务不可用' },
    })
  })
})
