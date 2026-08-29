import { apiRequest } from '../lib/apiClient'
import type { Document, DocumentListResponse } from '../types/document'

function documentBasePath(knowledgeBaseId: string) {
  return `/knowledge-bases/${knowledgeBaseId}/documents`
}

export function getDocuments(
  knowledgeBaseId: string,
  offset = 0,
  limit = 100,
): Promise<DocumentListResponse> {
  const query = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  })

  return apiRequest<DocumentListResponse>(
    `${documentBasePath(knowledgeBaseId)}?${query.toString()}`,
  )
}

export function uploadDocument(
  knowledgeBaseId: string,
  file: File,
): Promise<Document> {
  const body = new FormData()
  body.append('file', file)

  return apiRequest<Document>(documentBasePath(knowledgeBaseId), {
    method: 'POST',
    body,
  })
}

export function processDocument(
  knowledgeBaseId: string,
  documentId: string,
): Promise<Document> {
  return apiRequest<Document>(
    `${documentBasePath(knowledgeBaseId)}/${documentId}/process`,
    { method: 'POST' },
  )
}

export function deleteDocument(
  knowledgeBaseId: string,
  documentId: string,
): Promise<void> {
  return apiRequest<void>(
    `${documentBasePath(knowledgeBaseId)}/${documentId}`,
    { method: 'DELETE' },
  )
}
