import { zodResolver } from '@hookform/resolvers/zod'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate, useParams } from 'react-router-dom'
import type { z } from 'zod'
import { safeError } from '../../api/client'
import { conversationsApi } from '../../api/endpoints'
import { streamConversationMessage, type StreamEvent } from '../../api/sse'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { querySchema } from '../../schemas/forms'
import type { Citation, Message } from '../../types/api'
import { DocumentSelector } from '../documents/DocumentSelector'
import { CitationList } from './CitationList'
import { MessageBubble } from './MessageBubble'

type QueryValues = z.infer<typeof querySchema>
type StreamingMessage = { content: string; citations: Citation[]; requestId?: string; stage: string }

export function ConversationPage() {
  const { conversationId = '' } = useParams(); const navigate = useNavigate(); const client = useQueryClient()
  const [selected, setSelected] = useState<string[]>([]); const [streaming, setStreaming] = useState<StreamingMessage | null>(null); const [streamError, setStreamError] = useState(''); const [confirming, setConfirming] = useState(false); const [renaming, setRenaming] = useState(false); const [title, setTitle] = useState(''); const abortRef = useRef<AbortController | null>(null); const listRef = useRef<HTMLDivElement>(null); const pinnedRef = useRef(true)
  const conversation = useQuery({ queryKey: ['conversation', conversationId], queryFn: () => conversationsApi.get(conversationId), enabled: Boolean(conversationId) })
  useEffect(() => setTitle(conversation.data?.title || ''), [conversation.data?.title])
  const messages = useInfiniteQuery({ queryKey: ['messages', conversationId], queryFn: ({ pageParam }) => conversationsApi.messages(conversationId, pageParam), initialPageParam: 0, getNextPageParam: (last) => last.offset + last.limit < last.total ? last.offset + last.limit : undefined, enabled: Boolean(conversationId) })
  const history = messages.data?.pages.flatMap((page) => page.items) || []
  const form = useForm<QueryValues>({ resolver: zodResolver(querySchema), defaultValues: { query: '' } })
  const update = useMutation({ mutationFn: (body: { title?: string; archived?: boolean }) => conversationsApi.update(conversationId, body), onSuccess: () => { setRenaming(false); void client.invalidateQueries({ queryKey: ['conversation', conversationId] }); void client.invalidateQueries({ queryKey: ['conversations'] }) } })
  const remove = useMutation({ mutationFn: () => conversationsApi.remove(conversationId), onSuccess: () => { void client.invalidateQueries({ queryKey: ['conversations'] }); navigate('/') } })

  useEffect(() => { if (pinnedRef.current) listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' }) }, [history.length, streaming?.content])
  useEffect(() => () => abortRef.current?.abort(), [conversationId])

  async function refreshHistory() {
    await client.invalidateQueries({ queryKey: ['messages', conversationId] })
    await client.invalidateQueries({ queryKey: ['conversation', conversationId] })
    await client.invalidateQueries({ queryKey: ['conversations'] })
  }
  function handleEvent(event: StreamEvent) {
    if (event.event === 'request_started') setStreaming((value) => ({ content: value?.content || '', citations: [], requestId: event.data.request_id, stage: 'Starting retrieval' }))
    if (event.event === 'retrieval_completed') setStreaming((value) => ({ content: value?.content || '', citations: value?.citations || [], requestId: value?.requestId, stage: `Retrieved ${event.data.result_count} sources` }))
    if (event.event === 'token') setStreaming((value) => ({ content: (value?.content || '') + event.data.token, citations: value?.citations || [], requestId: value?.requestId, stage: 'Generating' }))
    if (event.event === 'citations') setStreaming((value) => ({ content: value?.content || '', citations: event.data.citations, requestId: value?.requestId, stage: 'Finalizing' }))
    if (event.event === 'error') setStreamError(event.data.message || 'Generation failed.')
    if (event.event === 'completed') setStreaming((value) => ({ content: value?.content || event.data.message.content, citations: value?.citations || event.data.message.citations, requestId: value?.requestId || event.data.message.request_id, stage: 'Completed' }))
  }
  const submit = form.handleSubmit(async ({ query }) => {
    if (abortRef.current) return
    setStreamError(''); setStreaming({ content: '', citations: [], stage: 'Connecting' })
    const controller = new AbortController(); abortRef.current = controller
    const idempotencyKey = crypto.randomUUID()
    try {
      await streamConversationMessage(conversationId, { query, document_ids: selected.length ? selected : undefined }, idempotencyKey, controller.signal, handleEvent)
      form.reset()
    } catch (error) {
      if (!(error instanceof DOMException && error.name === 'AbortError')) setStreamError(safeError(error))
    } finally {
      abortRef.current = null
      setStreaming(null)
      await refreshHistory()
    }
  })
  const keyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void submit() } }

  if (conversation.isError) return <div className="p-8 text-red-600" role="alert">{safeError(conversation.error)}</div>
  return <div className="flex h-[calc(100vh-3.5rem)] flex-col lg:h-screen"><header className="flex flex-wrap items-center justify-between gap-3 border-b bg-white px-5 py-3 dark:border-slate-800 dark:bg-slate-900"><div className="min-w-0 flex-1">{renaming ? <form className="flex max-w-lg gap-2" onSubmit={(event) => { event.preventDefault(); if (title.trim()) update.mutate({ title: title.trim() }) }}><label className="sr-only" htmlFor="conversation-title">Conversation title</label><input id="conversation-title" autoFocus maxLength={120} className="min-w-0 flex-1 rounded-lg border bg-transparent px-3 py-2" value={title} onChange={(event) => setTitle(event.target.value)} /><button className="rounded-lg bg-brand-600 px-3 py-2 text-sm text-white">Save</button><button type="button" className="rounded-lg border px-3 py-2 text-sm" onClick={() => setRenaming(false)}>Cancel</button></form> : <><h1 className="truncate text-lg font-semibold">{conversation.data?.title || 'Conversation'}</h1><p className="text-xs text-slate-500">Grounded answers with retrieved source citations</p></>}</div><div className="flex gap-2"><button aria-label="Rename conversation" className="rounded-lg border px-3 py-2 text-sm" onClick={() => setRenaming(true)}>Rename</button><button className="rounded-lg border px-3 py-2 text-sm" onClick={() => update.mutate({ archived: !conversation.data?.archived_at })}>{conversation.data?.archived_at ? 'Unarchive' : 'Archive'}</button><button aria-label="Delete conversation" className="rounded-lg border border-red-200 px-3 py-2 text-sm text-red-700" onClick={() => setConfirming(true)}>Delete</button></div></header>
    <div ref={listRef} onScroll={(event) => { const node = event.currentTarget; pinnedRef.current = node.scrollHeight - node.scrollTop - node.clientHeight < 100 }} className="min-h-0 flex-1 overflow-y-auto px-4 py-6" aria-live="polite"><div className="mx-auto max-w-4xl space-y-5">{messages.hasNextPage && <button className="mx-auto block text-sm text-brand-600 underline" onClick={() => messages.fetchNextPage()}>Load more messages</button>}{!messages.isLoading && !history.length && !streaming && <div className="py-20 text-center"><h2 className="text-xl font-semibold">Start a grounded conversation</h2><p className="mt-2 text-sm text-slate-500">Ask across all embedded documents or choose a specific scope below.</p></div>}{history.map((message: Message) => <MessageBubble key={message.id} message={message} />)}{streaming && <article className="flex justify-start"><div className="max-w-[min(46rem,90%)] rounded-2xl border bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900"><p className="whitespace-pre-wrap text-sm leading-6">{streaming.content || '…'}</p><CitationList citations={streaming.citations} /><p className="mt-2 text-xs text-slate-400">{streaming.stage}</p></div></article>}</div></div>
    <div className="border-t bg-white p-4 dark:border-slate-800 dark:bg-slate-900"><form className="mx-auto max-w-4xl" onSubmit={submit}><DocumentSelector selected={selected} onChange={setSelected} />{streamError && <p className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700" role="alert">{streamError} You can retry safely.</p>}<div className="mt-3 flex items-end gap-3"><label className="sr-only" htmlFor="chat-query">Ask a question</label><textarea id="chat-query" rows={2} maxLength={4000} className="min-h-12 flex-1 resize-y rounded-xl border bg-transparent px-4 py-3" placeholder="Ask about your documents…" onKeyDown={keyDown} {...form.register('query')} />{abortRef.current ? <button type="button" className="rounded-lg border border-red-300 px-4 py-3 text-red-700" onClick={() => abortRef.current?.abort()}>Stop</button> : <button disabled={Boolean(streaming)} className="rounded-lg bg-brand-600 px-5 py-3 font-medium text-white">Send</button>}</div>{form.formState.errors.query && <p className="mt-1 text-sm text-red-600">{form.formState.errors.query.message}</p>}<p className="mt-2 text-xs text-slate-400">Enter to send · Shift+Enter for a new line</p></form></div>
    <ConfirmDialog open={confirming} title="Delete conversation?" description="Messages and citation snapshots will be permanently removed. Documents are not affected." onClose={() => setConfirming(false)} onConfirm={() => { setConfirming(false); remove.mutate() }} />
  </div>
}
