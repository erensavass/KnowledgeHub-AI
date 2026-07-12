import { API_BASE_URL, apiRequest, ApiError } from './client'
import { getAccessToken, notifyUnauthorized } from '../stores/auth-token'
import type {
  Conversation, Document, DocumentChunk, EmbeddingStatusResponse, Message, Page, SearchResult, TokenResponse, User,
} from '../types/api'

export const authApi = {
  register: (body: { email: string; password: string }) => apiRequest<User>('/auth/register', { method: 'POST', body: JSON.stringify(body) }),
  login: (body: { email: string; password: string }) => apiRequest<TokenResponse>('/auth/login', { method: 'POST', body: JSON.stringify(body) }),
  me: (signal?: AbortSignal) => apiRequest<User>('/auth/me', { signal }),
}

export const documentsApi = {
  list: () => apiRequest<Document[]>('/documents'),
  get: (id: string) => apiRequest<Document>(`/documents/${id}`),
  process: (id: string) => apiRequest<Document>(`/documents/${id}/process`, { method: 'POST' }),
  embed: (id: string) => apiRequest(`/documents/${id}/embed`, { method: 'POST' }),
  embeddingStatus: (id: string) => apiRequest<EmbeddingStatusResponse>(`/documents/${id}/embedding-status`),
  chunks: (id: string) => apiRequest<Page<DocumentChunk>>(`/documents/${id}/chunks?limit=100&offset=0`),
  remove: (id: string) => apiRequest<void>(`/documents/${id}`, { method: 'DELETE' }),
  upload(file: File, onProgress: (value: number) => void, signal?: AbortSignal) {
    return new Promise<Document>((resolve, reject) => {
      const request = new XMLHttpRequest()
      request.open('POST', `${API_BASE_URL}/documents/upload`)
      const token = getAccessToken()
      if (token) request.setRequestHeader('Authorization', `Bearer ${token}`)
      request.upload.onprogress = (event) => event.lengthComputable && onProgress(Math.round(event.loaded / event.total * 100))
      request.onerror = () => reject(new ApiError(0, 'network_error', 'Upload failed. Check your connection.'))
      request.onload = () => {
        if (request.status === 401) notifyUnauthorized()
        if (request.status >= 200 && request.status < 300) resolve(JSON.parse(request.responseText) as Document)
        else {
          try {
            const body = JSON.parse(request.responseText) as { error?: { code?: string; message?: string } }
            reject(new ApiError(request.status, body.error?.code || 'upload_failed', body.error?.message || 'Upload failed.'))
          } catch { reject(new ApiError(request.status, 'upload_failed', 'Upload failed.')) }
        }
      }
      signal?.addEventListener('abort', () => { request.abort(); reject(new DOMException('Aborted', 'AbortError')) }, { once: true })
      const body = new FormData(); body.append('file', file); request.send(body)
    })
  },
}

export const conversationsApi = {
  list: (offset = 0, includeArchived = false) => apiRequest<Page<Conversation>>(`/conversations?limit=20&offset=${offset}&include_archived=${includeArchived}`),
  create: (title?: string) => apiRequest<Conversation>('/conversations', { method: 'POST', body: JSON.stringify(title ? { title } : {}) }),
  get: (id: string) => apiRequest<Conversation>(`/conversations/${id}`),
  update: (id: string, body: { title?: string; archived?: boolean }) => apiRequest<Conversation>(`/conversations/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  remove: (id: string) => apiRequest<void>(`/conversations/${id}`, { method: 'DELETE' }),
  messages: (id: string, offset = 0) => apiRequest<Page<Message>>(`/conversations/${id}/messages?limit=100&offset=${offset}`),
}

export const searchApi = {
  search: (body: { query: string; document_ids?: string[]; top_k: number; score_threshold: number }, signal?: AbortSignal) =>
    apiRequest<{ results: SearchResult[] }>('/search', { method: 'POST', body: JSON.stringify(body), signal }),
}
