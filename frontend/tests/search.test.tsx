import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { SearchPage } from '../src/features/documents/SearchPage'
import { jsonResponse } from './test-utils'

function renderSearch() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(<QueryClientProvider client={client}><SearchPage /></QueryClientProvider>)
}

test('renders semantic results and embedded document filters', async () => {
  vi.spyOn(globalThis, 'fetch')
    .mockResolvedValueOnce(jsonResponse([{ id: 'd1', original_filename: 'guide.pdf', embedding_status: 'embedded' }]))
    .mockResolvedValueOnce(jsonResponse({ results: [{ chunk_id: 'x', document_id: 'd1', chunk_index: 2, content: 'Signed token details', score: 0.9, page_number: 3, original_filename: 'guide.pdf', metadata: null }] }))
  renderSearch(); const actor = userEvent.setup()
  await actor.type(screen.getByLabelText('Search query'), 'authentication')
  await actor.click(await screen.findByText('guide.pdf'))
  await actor.click(screen.getByRole('button', { name: 'Search' }))
  expect(await screen.findByText('Signed token details')).toBeInTheDocument()
  expect(screen.getByText('Page 3 · Chunk 2')).toBeInTheDocument()
})

test('validates top k and score threshold before searching', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse([]))
  renderSearch(); const actor = userEvent.setup()
  await actor.type(screen.getByLabelText('Search query'), 'query')
  await actor.clear(screen.getByLabelText('Top K results')); await actor.type(screen.getByLabelText('Top K results'), '99')
  await actor.clear(screen.getByLabelText('Score threshold')); await actor.type(screen.getByLabelText('Score threshold'), '2')
  await actor.click(screen.getByRole('button', { name: 'Search' }))
  expect(await screen.findByText(/Choose 1–20/)).toBeInTheDocument()
})
