import { expect, test } from '@playwright/test'

const user = { id: 'u1', email: 'person@example.com', is_active: true, created_at: '2026-01-01T00:00:00Z' }

test('register, upload, process, embed, converse, stream, and view citations', async ({ page }) => {
  let documents: any[] = []
  let conversations: any[] = []
  let messages: any[] = []
  await page.route(/\/api\/(?:auth|documents|conversations|search)(?:\/|$)/, async (route) => {
    const url = new URL(route.request().url()); const path = url.pathname; const method = route.request().method()
    const json = (body: unknown, status = 200, contentType = 'application/json') => route.fulfill({ status, contentType, body: contentType === 'application/json' ? JSON.stringify(body) : String(body) })
    if (path === '/api/auth/register') return json(user, 201)
    if (path === '/api/auth/login') return json({ access_token: 'token', token_type: 'bearer' })
    if (path === '/api/auth/me') return json(user)
    if (path === '/api/documents' && method === 'GET') return json(documents)
    if (path === '/api/documents/upload') { documents = [{ id: 'd1', user_id: 'u1', original_filename: 'guide.txt', stored_filename: 'x', mime_type: 'text/plain', size_bytes: 4, status: 'uploaded', created_at: '', updated_at: '', processed_at: null, chunk_count: 0, processing_error_code: null, embedding_status: 'pending', embedding_error_code: null }]; return json(documents[0], 201) }
    if (path.endsWith('/process')) { documents[0].status = 'ready'; documents[0].chunk_count = 1; return json(documents[0]) }
    if (path.endsWith('/embed')) { documents[0].embedding_status = 'embedded'; return json({}) }
    if (path.endsWith('/embedding-status')) return json({ total_chunks: 1, embedded_chunks_in_postgres: 1, vectors_in_milvus: 1, remaining_chunks: 0, embedding_model: 'test', embedding_dimension: 3, status: 'embedded', consistent: true })
    if (path === '/api/conversations' && method === 'GET') return json({ items: conversations, total: conversations.length, limit: 20, offset: 0 })
    if (path === '/api/conversations' && method === 'POST') { const item = { id: 'c1', user_id: 'u1', title: 'New conversation', created_at: '', updated_at: '', last_message_at: '', archived_at: null }; conversations = [item]; return json(item, 201) }
    if (path === '/api/conversations/c1') return json(conversations[0])
    if (path.includes('/messages/stream')) { messages = [{ id: 'm2', conversation_id: 'c1', role: 'assistant', content: 'Grounded answer', status: 'completed', supported: true, provider: 'ollama', model: 'test', request_id: 'r1', created_at: '', citations: [{ citation_id: 'SOURCE_1', document_id: 'd1', original_filename: 'guide.txt', chunk_id: 'k1', chunk_index: 0, page_number: null, relevance_score: 0.9, excerpt: 'source excerpt' }] }]; return json('event: request_started\ndata: {"request_id":"r1"}\n\nevent: retrieval_completed\ndata: {"result_count":1}\n\nevent: token\ndata: {"token":"Grounded answer"}\n\nevent: citations\ndata: {"citations":[{"citation_id":"SOURCE_1","document_id":"d1","original_filename":"guide.txt","chunk_id":"k1","chunk_index":0,"page_number":null,"relevance_score":0.9,"excerpt":"source excerpt"}]}\n\nevent: completed\ndata: {"message":{"id":"m2","conversation_id":"c1","role":"assistant","content":"Grounded answer","status":"completed","supported":true,"provider":"ollama","model":"test","request_id":"r1","created_at":"","citations":[]}}\n\n', 200, 'text/event-stream') }
    if (path.endsWith('/messages')) return json({ items: messages, total: messages.length, limit: 100, offset: 0 })
    return json({})
  })
  await page.goto('/register'); await page.getByLabel('Email').fill(user.email); await page.getByLabel('Password').fill('StrongPassword123!'); await page.getByRole('button', { name: 'Register' }).click()
  await page.getByRole('link', { name: 'Documents', exact: true }).click(); await page.getByLabel('Upload PDF, DOCX, or TXT').setInputFiles({ name: 'guide.txt', mimeType: 'text/plain', buffer: Buffer.from('text') }); await expect(page.getByText('guide.txt')).toBeVisible()
  await page.getByRole('button', { name: 'Process' }).click(); await page.getByRole('button', { name: 'Embed' }).click()
  await page.getByRole('button', { name: /New conversation/ }).click(); await page.getByLabel('Ask a question').fill('How does it work?'); await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.getByText('Grounded answer')).toBeVisible(); await expect(page.getByText(/retrieved source excerpt/)).toBeVisible()
})
