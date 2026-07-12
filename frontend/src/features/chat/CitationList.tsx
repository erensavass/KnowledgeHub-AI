import type { Citation } from '../../types/api'

export function CitationList({ citations }: { citations: Citation[] }) {
  const unique = citations.filter((item, index, all) => all.findIndex((candidate) => candidate.chunk_id === item.chunk_id) === index)
  if (!unique.length) return null
  return <details className="mt-3 rounded-lg border border-slate-200 bg-white/70 dark:border-slate-700 dark:bg-slate-900/60"><summary className="cursor-pointer px-3 py-2 text-xs font-medium">{unique.length} retrieved source excerpt{unique.length === 1 ? '' : 's'}</summary><ol className="space-y-3 border-t p-3 dark:border-slate-700">{unique.map((citation) => <li key={citation.chunk_id} className="text-xs"><div className="flex flex-wrap justify-between gap-2 font-medium"><span>{citation.original_filename}{citation.page_number ? ` · page ${citation.page_number}` : ''}</span><span>Score {citation.relevance_score.toFixed(3)}</span></div><p className="mt-1 whitespace-pre-wrap leading-5 text-slate-600 dark:text-slate-300">{citation.excerpt}</p></li>)}</ol><p className="px-3 pb-3 text-[11px] text-slate-400">Citations identify retrieved chunks, not formal academic references.</p></details>
}
