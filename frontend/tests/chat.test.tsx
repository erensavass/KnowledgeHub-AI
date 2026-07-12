import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, vi } from 'vitest'
import { ConversationPage } from '../src/features/chat/ConversationPage'
import type { Message } from '../src/types/api'

const mocks = vi.hoisted(() => ({
  stream: vi.fn(),
  messages: vi.fn(),
  getConversation: vi.fn(),
  documents: vi.fn(),
}))

vi.mock('../src/api/endpoints', () => ({
  conversationsApi: {
    get: mocks.getConversation,
    messages: mocks.messages,
    update: vi.fn(),
    remove: vi.fn(),
  },
  documentsApi: { list: mocks.documents },
}))
vi.mock('../src/api/sse', () => ({ streamConversationMessage: mocks.stream }))

const conversation = { id: 'c1', user_id: 'u1', title: 'Security', created_at: '', updated_at: '', last_message_at: '', archived_at: null }
const assistant: Message = { id: 'm2', conversation_id: 'c1', role: 'assistant', content: 'Signed tokens', status: 'completed', supported: true, provider: 'ollama', model: 'test', request_id: 'request-123', created_at: '', citations: [{ citation_id: 'SOURCE_1', document_id: 'd1', original_filename: 'guide.pdf', chunk_id: 'chunk', chunk_index: 0, page_number: 2, relevance_score: 0.9, excerpt: 'Token source excerpt' }] }

beforeEach(() => {
  mocks.stream.mockReset()
  mocks.messages.mockReset()
  mocks.getConversation.mockReset()
  mocks.documents.mockReset().mockResolvedValue([])
})

function renderChat() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/chat/c1']}><Routes><Route path="/chat/:conversationId" element={<ConversationPage />} /></Routes></MemoryRouter></QueryClientProvider>)
}

test('renders incremental tokens, prevents duplicate submission, then restores authoritative history', async () => {
  let messages: Message[] = []
  let finish!: () => void
  let complete!: () => void
  const gate = new Promise<void>((resolve) => { finish = resolve })
  const completionGate = new Promise<void>((resolve) => { complete = resolve })
  mocks.getConversation.mockResolvedValue(conversation)
  mocks.messages.mockImplementation(async () => ({ items: messages, total: messages.length, limit: 100, offset: 0 }))
  mocks.stream.mockImplementation(async (_id, _body, _key, _signal, onEvent) => {
    onEvent({ event: 'request_started', data: { request_id: 'request-123' } })
    onEvent({ event: 'retrieval_completed', data: { result_count: 1 } })
    onEvent({ event: 'token', data: { token: 'Signed ' } })
    await gate
    onEvent({ event: 'token', data: { token: 'tokens' } })
    onEvent({ event: 'citations', data: { citations: assistant.citations } })
    await completionGate
    messages = [assistant]
    onEvent({ event: 'completed', data: { message: assistant } })
  })
  renderChat(); const actor = userEvent.setup()
  await actor.type(await screen.findByLabelText('Ask a question'), 'How?')
  await actor.click(screen.getByRole('button', { name: 'Send' }))
  expect(await screen.findByText('Signed')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument()
  await actor.type(screen.getByLabelText('Ask a question'), '{enter}')
  expect(mocks.stream).toHaveBeenCalledTimes(1)
  finish()
  expect(await screen.findByText('Signed tokens')).toBeInTheDocument()
  expect(await screen.findByText(/retrieved source excerpt/)).toBeInTheDocument()
  expect(screen.getByText('Token source excerpt')).toBeInTheDocument()
  complete()
  await waitFor(() => expect(mocks.messages).toHaveBeenCalledTimes(2))
  const idempotencyKey = mocks.stream.mock.calls[0][2]
  expect(idempotencyKey).toMatch(/[0-9a-f-]{20,}/)
})

test('announces safe stream errors and refreshes history', async () => {
  mocks.getConversation.mockResolvedValue(conversation)
  mocks.messages.mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 })
  mocks.stream.mockImplementation(async (_id, _body, _key, _signal, onEvent) => {
    onEvent({ event: 'error', data: { code: 'generation_failed', message: 'Generation failed' } })
  })
  renderChat(); const actor = userEvent.setup()
  await actor.type(await screen.findByLabelText('Ask a question'), 'How?')
  await actor.click(screen.getByRole('button', { name: 'Send' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Generation failed')
  expect(mocks.messages).toHaveBeenCalledTimes(2)
})

test('stop generation aborts the active authenticated stream', async () => {
  mocks.getConversation.mockResolvedValue(conversation)
  mocks.messages.mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 })
  let observedSignal: AbortSignal | undefined
  mocks.stream.mockImplementation((_id, _body, _key, signal) => {
    observedSignal = signal
    return new Promise((_resolve, reject) => signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true }))
  })
  renderChat(); const actor = userEvent.setup()
  await actor.type(await screen.findByLabelText('Ask a question'), 'How?')
  await actor.click(screen.getByRole('button', { name: 'Send' }))
  await actor.click(await screen.findByRole('button', { name: 'Stop' }))
  await waitFor(() => expect(observedSignal?.aborted).toBe(true))
  expect(mocks.stream).toHaveBeenCalledTimes(1)
})
