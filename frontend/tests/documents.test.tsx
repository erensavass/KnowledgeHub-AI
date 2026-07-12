import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { DocumentsPage } from '../src/features/documents/DocumentsPage'
import { validateUpload } from '../src/schemas/forms'
import { jsonResponse } from './test-utils'

const document = { id: 'd1', user_id: 'u1', original_filename: 'guide.pdf', stored_filename: 'x.pdf', mime_type: 'application/pdf', size_bytes: 1024, status: 'ready', created_at: '', updated_at: '', processed_at: '', chunk_count: 3, processing_error_code: null, embedding_status: 'embedded', embedding_error_code: null }

test('validates file extension, emptiness, and size before upload', () => {
  expect(validateUpload(new File(['x'], 'bad.exe'), 20)).toMatch(/PDF/)
  expect(validateUpload(new File([], 'empty.txt'), 20)).toMatch(/empty/)
  expect(validateUpload(new File([new Uint8Array(10)], 'good.txt'), 20)).toBeNull()
  expect(validateUpload(new File([new Uint8Array(10)], 'large.txt'), 0.000001)).toMatch(/smaller/)
})

test('renders document and embedding status with accessible lifecycle actions', async () => {
  vi.spyOn(globalThis, 'fetch')
    .mockResolvedValueOnce(jsonResponse([document]))
    .mockResolvedValueOnce(jsonResponse({ total_chunks: 3, embedded_chunks_in_postgres: 3, vectors_in_milvus: 3, remaining_chunks: 0, embedding_model: 'test', embedding_dimension: 3, status: 'embedded', consistent: true }))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><DocumentsPage /></QueryClientProvider>)
  expect(await screen.findByText('guide.pdf')).toBeInTheDocument()
  expect(screen.getByText('embedded')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Reprocess' })).toBeEnabled()
  expect(screen.getByRole('button', { name: 'Re-embed' })).toBeEnabled()
})

test('deletion requires confirmation and dialog offers focused cancel', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(jsonResponse([document]))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><DocumentsPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: 'Delete' }))
  expect(screen.getByRole('dialog')).toHaveAttribute('open')
  expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus()
})
