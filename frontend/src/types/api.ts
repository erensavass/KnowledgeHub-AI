export type User = { id: string; email: string; is_active: boolean; created_at: string }
export type TokenResponse = { access_token: string; token_type: string }

export type DocumentStatus = 'uploaded' | 'processing' | 'ready' | 'failed'
export type EmbeddingStatus = 'pending' | 'embedding' | 'embedded' | 'embedding_failed'
export type Document = {
  id: string
  user_id: string
  original_filename: string
  stored_filename: string
  mime_type: string
  size_bytes: number
  status: DocumentStatus
  created_at: string
  updated_at: string
  processed_at: string | null
  chunk_count: number
  processing_error_code: string | null
  embedding_status: EmbeddingStatus
  embedding_error_code: string | null
}
export type EmbeddingStatusResponse = {
  total_chunks: number
  embedded_chunks_in_postgres: number
  vectors_in_milvus: number
  remaining_chunks: number
  embedding_model: string
  embedding_dimension: number
  status: EmbeddingStatus
  consistent: boolean
}
export type DocumentChunk = {
  id: string
  document_id: string
  chunk_index: number
  content: string
  character_count: number
  token_count: number
  page_number: number | null
  metadata_json: Record<string, unknown> | null
  created_at: string
}

export type Conversation = {
  id: string
  user_id: string
  title: string
  created_at: string
  updated_at: string
  last_message_at: string
  archived_at: string | null
}
export type Citation = {
  citation_id: string
  document_id: string
  original_filename: string
  chunk_id: string
  chunk_index: number
  page_number: number | null
  relevance_score: number
  excerpt: string
}
export type Message = {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  status: 'pending' | 'completed' | 'failed'
  supported: boolean | null
  provider: string | null
  model: string | null
  request_id: string
  created_at: string
  citations: Citation[]
}
export type Page<T> = { items: T[]; total: number; limit: number; offset: number }

export type SearchResult = {
  chunk_id: string
  document_id: string
  chunk_index: number
  content: string
  score: number
  page_number: number | null
  original_filename: string
  metadata: Record<string, unknown> | null
}
export type ApiErrorBody = {
  error?: { code?: string; message?: string; details?: unknown }
}
