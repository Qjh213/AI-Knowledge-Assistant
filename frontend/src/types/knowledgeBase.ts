export interface KnowledgeBase {
  id: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
}

export interface KnowledgeBaseListResponse {
  items: KnowledgeBase[]
  total: number
  offset: number
  limit: number
}

export interface KnowledgeBaseCreate {
  name: string
  description?: string | null
}
