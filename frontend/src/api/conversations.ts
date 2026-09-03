import { API_BASE_URL, ApiError, apiRequest, authenticatedHeaders, notifyAuthError } from '../lib/apiClient'
import type {
  Conversation,
  ConversationListResponse,
  MessageCreate,
  MessageListResponse,
  MessageTurnResponse,
  ConversationStreamEvent,
  RecentConversationListResponse,
} from '../types/conversation'

function conversationsPath(knowledgeBaseId: string) {
  return `/knowledge-bases/${knowledgeBaseId}/conversations`
}

export function getRecentConversations(
  offset = 0,
  limit = 50,
): Promise<RecentConversationListResponse> {
  const query = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  })
  return apiRequest<RecentConversationListResponse>(
    `/conversations/recent?${query.toString()}`,
  )
}

export function getConversations(
  knowledgeBaseId: string,
  offset = 0,
  limit = 100,
): Promise<ConversationListResponse> {
  const query = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  })

  return apiRequest<ConversationListResponse>(
    `${conversationsPath(knowledgeBaseId)}?${query.toString()}`,
  )
}

export function createConversation(
  knowledgeBaseId: string,
): Promise<Conversation> {
  return apiRequest<Conversation>(conversationsPath(knowledgeBaseId), {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export function getConversation(
  knowledgeBaseId: string,
  conversationId: string,
): Promise<Conversation> {
  return apiRequest<Conversation>(
    `${conversationsPath(knowledgeBaseId)}/${conversationId}`,
  )
}

export function deleteConversation(
  knowledgeBaseId: string,
  conversationId: string,
): Promise<void> {
  return apiRequest<void>(
    `${conversationsPath(knowledgeBaseId)}/${conversationId}`,
    { method: 'DELETE' },
  )
}

export function getMessages(
  knowledgeBaseId: string,
  conversationId: string,
  offset = 0,
  limit = 100,
): Promise<MessageListResponse> {
  const query = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  })

  return apiRequest<MessageListResponse>(
    `${conversationsPath(knowledgeBaseId)}/${conversationId}/messages?${query.toString()}`,
  )
}

export function sendMessage(
  knowledgeBaseId: string,
  conversationId: string,
  data: MessageCreate,
): Promise<MessageTurnResponse> {
  return apiRequest<MessageTurnResponse>(
    `${conversationsPath(knowledgeBaseId)}/${conversationId}/messages`,
    {
      method: 'POST',
      body: JSON.stringify(data),
    },
  )
}

function parseStreamEvent(block: string): ConversationStreamEvent | null {
  let eventName = ''
  const dataLines: string[] = []

  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) {
      eventName = line.slice('event:'.length).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trimStart())
    }
  }

  if (!eventName || dataLines.length === 0) {
    return null
  }

  const supportedEvents = new Set([
    'user_message',
    'citations',
    'token',
    'done',
    'error',
  ])

  if (!supportedEvents.has(eventName)) {
    return null
  }

  return {
    event: eventName,
    data: JSON.parse(dataLines.join('\n')),
  } as ConversationStreamEvent
}

export async function streamMessage(
  knowledgeBaseId: string,
  conversationId: string,
  data: MessageCreate,
  onEvent: (event: ConversationStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}${conversationsPath(knowledgeBaseId)}/${conversationId}/messages/stream`,
    {
      method: 'POST',
      headers: authenticatedHeaders({ 'Content-Type': 'application/json' }),
      credentials: 'include',
      body: JSON.stringify(data),
      signal,
    },
  )

  if (!response.ok) {
    notifyAuthError(response)
    let detail = `请求失败（HTTP ${response.status}）`

    try {
      const body = (await response.json()) as { detail?: string }
      detail = body.detail ?? detail
    } catch {
      // The server may return an empty or non-JSON error response.
    }

    throw new ApiError(detail, response.status)
  }

  if (!response.body) {
    throw new Error('浏览器无法读取流式响应。')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })

      let boundary = buffer.indexOf('\n\n')
      while (boundary !== -1) {
        const block = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        const event = parseStreamEvent(block)

        if (event) {
          onEvent(event)

          if (event.event === 'error') {
            throw new Error(event.data.detail)
          }
        }

        boundary = buffer.indexOf('\n\n')
      }

      if (done) {
        break
      }
    }

    const finalEvent = parseStreamEvent(buffer.trim())
    if (finalEvent) {
      onEvent(finalEvent)

      if (finalEvent.event === 'error') {
        throw new Error(finalEvent.data.detail)
      }
    }
  } finally {
    reader.releaseLock()
  }
}
