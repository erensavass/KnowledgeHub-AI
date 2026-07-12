import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { safeError } from '../../api/client'
import { documentsApi } from '../../api/endpoints'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { validateUpload } from '../../schemas/forms'
import type { Document } from '../../types/api'

const statusStyle: Record<string, string> = {
  uploaded: 'bg-blue-50 text-blue-700', processing: 'bg-amber-50 text-amber-700', ready: 'bg-emerald-50 text-emerald-700', failed: 'bg-red-50 text-red-700',
  pending: 'bg-slate-100 text-slate-700', embedding: 'bg-amber-50 text-amber-700', embedded: 'bg-emerald-50 text-emerald-700', embedding_failed: 'bg-red-50 text-red-700',
}
const label = (value: string) => value.replaceAll('_', ' ')

function DocumentRow({ document }: { document: Document }) {
  const client = useQueryClient(); const [confirming, setConfirming] = useState(false); const [error, setError] = useState(''); const [showChunks, setShowChunks] = useState(false)
  const refresh = () => client.invalidateQueries({ queryKey: ['documents'] })
  const process = useMutation({ mutationFn: () => documentsApi.process(document.id), onSuccess: refresh, onError: (e) => setError(safeError(e)) })
  const embed = useMutation({ mutationFn: () => documentsApi.embed(document.id), onSuccess: refresh, onError: (e) => setError(safeError(e)) })
  const remove = useMutation({ mutationFn: () => documentsApi.remove(document.id), onSuccess: refresh, onError: (e) => setError(safeError(e)) })
  const embedding = useQuery({ queryKey: ['embedding-status', document.id], queryFn: () => documentsApi.embeddingStatus(document.id), enabled: document.status === 'ready' })
  const chunks = useQuery({ queryKey: ['document-chunks', document.id], queryFn: () => documentsApi.chunks(document.id), enabled: showChunks })
  const busy = process.isPending || embed.isPending || remove.isPending
  return <article className="rounded-xl border bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><h2 className="font-semibold">{document.original_filename}</h2><p className="mt-1 text-xs text-slate-500">{(document.size_bytes / 1024).toFixed(1)} KB · {document.chunk_count} chunks</p></div><div className="flex flex-wrap gap-2"><span className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${statusStyle[document.status]}`}>{label(document.status)}</span><span className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${statusStyle[document.embedding_status]}`}>{label(document.embedding_status)}</span></div></div>
    {document.status === 'failed' && <p className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700" role="alert">Document processing failed. You can retry processing.</p>}
    {document.embedding_status === 'embedding_failed' && <p className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">Embedding failed. Retry when the vector service is available.</p>}
    {embedding.data && <p className="mt-3 text-xs text-slate-500">Embedding coverage: {embedding.data.embedded_chunks_in_postgres}/{embedding.data.total_chunks} · {embedding.data.consistent ? 'consistent' : 'reconciliation needed'}</p>}
    {error && <p role="alert" className="mt-3 text-sm text-red-600">{error}</p>}
    <div className="mt-4 flex flex-wrap gap-2"><button className="rounded-lg border px-3 py-2 text-sm" disabled={busy || document.status === 'processing'} onClick={() => process.mutate()}>{document.status === 'ready' ? 'Reprocess' : 'Process'}</button><button className="rounded-lg bg-brand-600 px-3 py-2 text-sm text-white" disabled={busy || document.status !== 'ready' || document.embedding_status === 'embedding'} onClick={() => embed.mutate()}>{document.embedding_status === 'embedded' ? 'Re-embed' : 'Embed'}</button><button className="rounded-lg border px-3 py-2 text-sm" disabled={document.status !== 'ready'} onClick={() => setShowChunks((value) => !value)}>{showChunks ? 'Hide chunks' : 'View chunks'}</button><button className="rounded-lg border border-red-200 px-3 py-2 text-sm text-red-700" disabled={busy} onClick={() => setConfirming(true)}>Delete</button></div>
    {showChunks && <div className="mt-4 max-h-64 space-y-3 overflow-y-auto border-t pt-4 dark:border-slate-700">{chunks.isLoading && <p className="text-sm">Loading chunks…</p>}{chunks.data?.items.map((chunk) => <div key={chunk.id} className="rounded-lg bg-slate-50 p-3 text-sm dark:bg-slate-800"><p className="mb-1 text-xs font-medium text-slate-500">Chunk {chunk.chunk_index}{chunk.page_number ? ` · page ${chunk.page_number}` : ''}</p><p className="line-clamp-4 whitespace-pre-wrap">{chunk.content}</p></div>)}</div>}
    <ConfirmDialog open={confirming} title="Delete document?" description="This removes the document and its vectors. Conversation citation snapshots remain." onClose={() => setConfirming(false)} onConfirm={() => { setConfirming(false); remove.mutate() }} />
  </article>
}

export function DocumentsPage() {
  const client = useQueryClient(); const input = useRef<HTMLInputElement>(null); const [progress, setProgress] = useState<number | null>(null); const [error, setError] = useState('')
  const documents = useQuery({ queryKey: ['documents'], queryFn: documentsApi.list })
  const upload = useMutation({ mutationFn: (file: File) => documentsApi.upload(file, setProgress), onSuccess: () => { setProgress(null); setError(''); if (input.current) input.current.value = ''; void client.invalidateQueries({ queryKey: ['documents'] }) }, onError: (e) => { setProgress(null); setError(safeError(e)) } })
  const select = (file?: File) => { if (!file) return; const max = Number(import.meta.env.VITE_MAX_UPLOAD_SIZE_MB || 20); const validation = validateUpload(file, max); if (validation) { setError(validation); return } setError(''); setProgress(0); upload.mutate(file) }
  return <section className="mx-auto max-w-6xl px-5 py-8"><div className="flex flex-wrap items-end justify-between gap-4"><div><h1 className="text-2xl font-semibold">Documents</h1><p className="mt-1 text-sm text-slate-500">Upload source material, then process and embed it for retrieval.</p></div><label className="cursor-pointer rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-medium text-white">Upload document<input ref={input} className="sr-only" aria-label="Upload PDF, DOCX, or TXT" type="file" accept=".pdf,.docx,.txt" disabled={upload.isPending} onChange={(event) => select(event.target.files?.[0])} /></label></div>
    {progress !== null && <div className="mt-5" aria-live="polite"><div className="mb-1 flex justify-between text-sm"><span>Uploading…</span><span>{progress}%</span></div><progress className="h-2 w-full" max="100" value={progress} /></div>}
    {error && <p role="alert" className="mt-5 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    {documents.isLoading && <p className="mt-8" role="status">Loading documents…</p>}{documents.isError && <p className="mt-8 text-red-600" role="alert">{safeError(documents.error)}</p>}
    <div className="mt-6 grid gap-4 lg:grid-cols-2">{documents.data?.map((document) => <DocumentRow key={document.id} document={document} />)}</div>
    {!documents.isLoading && !documents.data?.length && <div className="mt-12 rounded-xl border border-dashed p-10 text-center"><h2 className="font-semibold">No documents yet</h2><p className="mt-2 text-sm text-slate-500">Upload a PDF, DOCX, or UTF-8 text file to get started.</p></div>}
    <p className="mt-6 text-xs text-slate-500">Client checks improve feedback; the backend remains the source of truth for file validation.</p>
  </section>
}
