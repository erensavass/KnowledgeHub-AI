import { vi } from 'vitest'
import { parseSseFrames, streamConversationMessage, type StreamEvent } from '../src/api/sse'
import { setAccessToken } from '../src/stores/auth-token'

test('parses partial and malformed frames while preserving event order', () => {
  const first = parseSseFrames('event: request_started\ndata: {"request_id":"r1"}\n\nevent: token\ndata: {"token":"Hel')
  expect(first.events).toEqual([{ event: 'request_started', data: { request_id: 'r1' } }])
  const second = parseSseFrames(first.remainder + 'lo"}\n\nevent: token\ndata: broken\n\nevent: token\ndata: {"token":"!"}\n\n')
  expect(second.events).toEqual([{ event: 'token', data: { token: 'Hello' } }, { event: 'token', data: { token: '!' } }])
})

test('streams tokens and citations with authentication and an idempotency key', async () => {
  setAccessToken('token')
  const encoder = new TextEncoder()
  const stream = new ReadableStream({ start(controller) { controller.enqueue(encoder.encode('event: token\ndata: {"token":"Hi"}\n\nevent: citations\ndata: {"citations":[]}\n\n')); controller.close() } })
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(stream, { status: 200 }))
  const events: StreamEvent[] = []
  await streamConversationMessage('c1', { query: 'hello' }, 'unique-key', new AbortController().signal, (event) => events.push(event))
  const headers = fetch.mock.calls[0][1]?.headers as Headers
  expect(headers.get('Authorization')).toBe('Bearer token')
  expect(headers.get('Idempotency-Key')).toBe('unique-key')
  expect(events.map((item) => item.event)).toEqual(['token', 'citations'])
})

test('supports cancellation without reconnecting or replaying', async () => {
  const controller = new AbortController(); controller.abort()
  const fetch = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new DOMException('Aborted', 'AbortError'))
  await expect(streamConversationMessage('c1', { query: 'x' }, 'key', controller.signal, () => undefined)).rejects.toMatchObject({ name: 'AbortError' })
  expect(fetch).toHaveBeenCalledTimes(1)
})
