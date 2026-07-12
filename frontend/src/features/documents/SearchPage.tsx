import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import type { z } from 'zod'
import { safeError } from '../../api/client'
import { searchApi } from '../../api/endpoints'
import { searchSchema } from '../../schemas/forms'
import { DocumentSelector } from './DocumentSelector'

type Values = z.infer<typeof searchSchema>
export function SearchPage() {
  const [selected, setSelected] = useState<string[]>([])
  const form = useForm<Values>({ resolver: zodResolver(searchSchema), defaultValues: { query: '', top_k: 5, score_threshold: 0 } })
  const search = useMutation({ mutationFn: (values: Values) => searchApi.search({ ...values, document_ids: selected.length ? selected : undefined }) })
  return <section className="mx-auto max-w-5xl px-5 py-8"><h1 className="text-2xl font-semibold">Semantic search</h1><p className="mt-1 text-sm text-slate-500">Find relevant source chunks without generating an AI answer.</p>
    <form className="mt-6 rounded-xl border bg-white p-5 dark:border-slate-800 dark:bg-slate-900" onSubmit={form.handleSubmit((values) => search.mutate(values))}><label className="block text-sm font-medium">Search query<input className="mt-1 w-full rounded-lg border bg-transparent px-3 py-2" {...form.register('query')} /></label>{form.formState.errors.query && <p className="mt-1 text-sm text-red-600">{form.formState.errors.query.message}</p>}<div className="mt-4 grid gap-4 sm:grid-cols-2"><label className="text-sm font-medium">Results<input aria-label="Top K results" type="number" className="mt-1 w-full rounded-lg border bg-transparent px-3 py-2" {...form.register('top_k')} /></label><label className="text-sm font-medium">Minimum score<input aria-label="Score threshold" type="number" step="0.05" className="mt-1 w-full rounded-lg border bg-transparent px-3 py-2" {...form.register('score_threshold')} /></label></div>{(form.formState.errors.top_k || form.formState.errors.score_threshold) && <p className="mt-2 text-sm text-red-600">Choose 1–20 results and a score from -1 to 1.</p>}<div className="mt-4"><DocumentSelector selected={selected} onChange={setSelected} /></div><button disabled={search.isPending} className="mt-5 rounded-lg bg-brand-600 px-5 py-2.5 font-medium text-white">{search.isPending ? 'Searching…' : 'Search'}</button></form>
    {search.isError && <p role="alert" className="mt-5 rounded-lg bg-red-50 p-3 text-red-700">{safeError(search.error)}</p>}
    {search.data && !search.data.results.length && <div className="mt-8 text-center text-slate-500">No relevant chunks found.</div>}
    <div className="mt-6 space-y-4">{search.data?.results.map((result) => <article key={result.chunk_id} className="rounded-xl border bg-white p-5 dark:border-slate-800 dark:bg-slate-900"><div className="flex flex-wrap justify-between gap-2"><h2 className="font-medium">{result.original_filename}</h2><span className="text-sm font-mono text-brand-600">{result.score.toFixed(3)}</span></div><p className="mt-1 text-xs text-slate-500">{result.page_number ? `Page ${result.page_number} · ` : ''}Chunk {result.chunk_index}</p><p className="mt-3 whitespace-pre-wrap text-sm leading-6">{result.content}</p></article>)}</div>
  </section>
}
