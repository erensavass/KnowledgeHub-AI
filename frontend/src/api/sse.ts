import { API_BASE_URL, ApiError } from './client'
import { getAccessToken, notifyUnauthorized } from '../stores/auth-token'
import type { Citation, Message } from '../types/api'

export type StreamEvent =
  | { event: 'request_started'; data: { request_id: string } }
  | { event: 'retrieval_completed'; data: { result_count: number } }
  | { event: 'token'; data: { token: string } }
  | { event: 'citations'; data: { citations: Citation[] } }
  | { event: 'completed'; data: { message: Message } }
  | { event: 'error'; data: { code: string; message: string } }

export function parseSseFrames(buffer: string): { events: StreamEvent[]; remainder: string } {
  const normalized = buffer.replace(/\r\n/g, '\n')
  const blocks = normalized.split('\n\n')
  const remainder = blocks.pop() || ''
  const events: StreamEvent[] = []
  for (const block of blocks) {
    if (!block || block.startsWith(':')) continue
    let event = ''
    const data: string[] = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
    }
    if (!event || !data.length) continue
    try {
      const payload = JSON.parse(data.join('\n'))
      if (['request_started', 'retrieval_completed', 'token', 'citations', 'completed', 'error'].includes(event)) {
        events.push({ event, data: payload } as StreamEvent)
      }
    } catch { /* malformed server event is ignored without breaking later frames */ }
  }
  return { events, remainder }
}

export async function streamConversationMessage(
  conversationId: string,
  body: { query: string; document_ids?: string[] },
  idempotencyKey: string,
  signal: AbortSignal,
  onEvent: (event: StreamEvent) => void,
) {
  const headers = new Headers({ 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey })
  const token = getAccessToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}/messages/stream`, {
    method: 'POST', headers, body: JSON.stringify(body), signal,
  })
  if (response.status === 401) notifyUnauthorized()
  if (!response.ok || !response.body) throw new ApiError(response.status, 'stream_failed', 'Streaming could not start.')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const parsed = parseSseFrames(buffer)
    buffer = parsed.remainder
    parsed.events.forEach(onEvent)
    if (done) break
  }
}
