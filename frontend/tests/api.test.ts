import { vi } from 'vitest'
import { conversationsApi, documentsApi, searchApi } from '../src/api/endpoints'
import { jsonResponse } from './test-utils'

test('conversation actions use centralized typed endpoints', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => jsonResponse({ id: 'c1' }))
  await conversationsApi.create('Title')
  await conversationsApi.update('c1', { title: 'Renamed', archived: true })
  await conversationsApi.remove('c1')
  expect(fetch.mock.calls[0][0]).toBe('/api/conversations')
  expect(fetch.mock.calls[1][0]).toBe('/api/conversations/c1')
  expect(fetch.mock.calls[1][1]?.method).toBe('PATCH')
  expect(fetch.mock.calls[2][1]?.method).toBe('DELETE')
})

test('document processing and embedding actions are not duplicated in components', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => jsonResponse({}))
  await documentsApi.process('d1'); await documentsApi.embed('d1'); await documentsApi.remove('d1')
  expect(fetch.mock.calls.map((call) => [call[0], call[1]?.method])).toEqual([
    ['/api/documents/d1/process', 'POST'], ['/api/documents/d1/embed', 'POST'], ['/api/documents/d1', 'DELETE'],
  ])
})

test('semantic search sends filters and validated controls', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ results: [] }))
  await searchApi.search({ query: 'tokens', document_ids: ['d1'], top_k: 5, score_threshold: 0.2 })
  const body = JSON.parse(String(fetch.mock.calls[0][1]?.body))
  expect(body).toEqual({ query: 'tokens', document_ids: ['d1'], top_k: 5, score_threshold: 0.2 })
})
