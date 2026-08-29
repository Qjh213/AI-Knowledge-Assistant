import { apiRequest } from '../lib/apiClient'
import type {
  Conversation,
  ConversationListResponse,
  MessageCreate,
  MessageListResponse,
  MessageTurnResponse,
} from '../types/conversation'

function conversationsPath(knowledgeBaseId: string) {
  return `/knowledge-bases/${knowledgeBaseId}/conversations`
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
