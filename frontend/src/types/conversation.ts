export interface Conversation {
  id: string
  knowledge_base_id: string
  title: string | null
  created_at: string
  updated_at: string
}

export interface ConversationListResponse {
  items: Conversation[]
  total: number
  offset: number
  limit: number
}

export interface RecentConversation extends Conversation {
  knowledge_base_name: string
}

export interface RecentConversationListResponse {
  items: RecentConversation[]
  total: number
  offset: number
  limit: number
}

export interface RagCitation {
  reference: number
  chunk_id: string
  document_id: string
  original_filename: string
  page_number: number | null
  content: string
  score: number
}

export type MessageRole = 'user' | 'assistant'

export interface Message {
  id: string
  conversation_id: string
  role: MessageRole
  content: string
  sources: RagCitation[] | null
  created_at: string
  updated_at: string
}

export interface MessageListResponse {
  items: Message[]
  total: number
  offset: number
  limit: number
}

export interface MessageCreate {
  content: string
  retrieval_limit?: number
  min_score?: number
}

export interface MessageTurnResponse {
  conversation_id: string
  user_message: Message
  assistant_message: Message
}

export type ConversationStreamEvent =
  | {
      event: 'user_message'
      data: { message: Message }
    }
  | {
      event: 'citations'
      data: { citations: RagCitation[] }
    }
  | {
      event: 'token'
      data: { content: string }
    }
  | {
      event: 'done'
      data: { message: Message }
    }
  | {
      event: 'error'
      data: { detail: string }
    }
