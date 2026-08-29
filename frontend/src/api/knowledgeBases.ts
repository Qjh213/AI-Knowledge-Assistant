import { apiRequest } from '../lib/apiClient'
import type {
  KnowledgeBase,
  KnowledgeBaseCreate,
  KnowledgeBaseListResponse,
} from '../types/knowledgeBase'

export function getKnowledgeBases(
  offset = 0,
  limit = 100,
): Promise<KnowledgeBaseListResponse> {
  const query = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  })

  return apiRequest<KnowledgeBaseListResponse>(
    `/knowledge-bases?${query.toString()}`,
  )
}

export function createKnowledgeBase(
  data: KnowledgeBaseCreate,
): Promise<KnowledgeBase> {
  return apiRequest<KnowledgeBase>('/knowledge-bases', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
