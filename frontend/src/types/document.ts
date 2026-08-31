export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed'
export type DocumentParser = 'local' | 'mineru'

export interface Document {
  id: string
  knowledge_base_id: string
  original_filename: string
  mime_type: string
  file_size: number
  checksum: string
  status: DocumentStatus
  error_message: string | null
  chunk_count: number
  parser: DocumentParser
  external_task_id: string | null
  processing_progress: number
  created_at: string
  updated_at: string
}

export interface DocumentListResponse {
  items: Document[]
  total: number
  offset: number
  limit: number
}
