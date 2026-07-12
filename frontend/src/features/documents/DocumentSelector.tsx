import { useQuery } from '@tanstack/react-query'
import { documentsApi } from '../../api/endpoints'

export function DocumentSelector({ selected, onChange }: { selected: string[]; onChange(ids: string[]): void }) {
  const documents = useQuery({ queryKey: ['documents'], queryFn: documentsApi.list })
  const embedded = documents.data?.filter((item) => item.embedding_status === 'embedded') || []
  return <div><div className="flex items-center justify-between"><p className="text-sm font-medium">Document scope</p>{selected.length > 0 && <button type="button" className="text-xs text-brand-600 underline" onClick={() => onChange([])}>Clear filters</button>}</div>
    <div className="mt-2 max-h-36 space-y-1 overflow-y-auto rounded-lg border p-2 dark:border-slate-700">{embedded.map((item) => <label key={item.id} className="flex items-center gap-2 rounded p-1.5 text-sm hover:bg-slate-50 dark:hover:bg-slate-800"><input type="checkbox" checked={selected.includes(item.id)} onChange={(event) => onChange(event.target.checked ? [...selected, item.id] : selected.filter((id) => id !== item.id))} /><span className="truncate">{item.original_filename}</span></label>)}{!embedded.length && <p className="p-2 text-xs text-slate-500">Embed a document to make it selectable.</p>}</div>
    {selected.length > 0 && <p className="mt-2 text-xs text-slate-500">{selected.length} embedded document{selected.length === 1 ? '' : 's'} selected</p>}
  </div>
}
