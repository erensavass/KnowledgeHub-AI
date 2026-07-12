import { render, screen } from '@testing-library/react'
import { CitationList } from '../src/features/chat/CitationList'

test('deduplicates citations, preserves order, and renders excerpts as plain text', () => {
  const citation = { citation_id: 'SOURCE_1', document_id: 'd', original_filename: 'guide.pdf', chunk_id: 'chunk', chunk_index: 0, page_number: 2, relevance_score: 0.92, excerpt: '<img src=x onerror=alert(1)>' }
  const { container } = render(<CitationList citations={[citation, { ...citation, citation_id: 'SOURCE_2' }]} />)
  expect(screen.getByText(/1 retrieved source excerpt/)).toBeInTheDocument()
  expect(screen.getByText('guide.pdf · page 2')).toBeInTheDocument()
  expect(screen.getByText(citation.excerpt)).toBeInTheDocument()
  expect(container.querySelector('img')).toBeNull()
})
