import type { Message } from '../../types/api'
import { CitationList } from './CitationList'

export function MessageBubble({ message }: { message: Message }) {
  const assistant = message.role === 'assistant'
  return <article className={`flex ${assistant ? 'justify-start' : 'justify-end'}`} aria-label={`${message.role} message`}><div className={`max-w-[min(46rem,90%)] rounded-2xl px-4 py-3 ${assistant ? message.supported === false ? 'border border-amber-300 bg-amber-50 text-amber-950 dark:bg-amber-950 dark:text-amber-100' : 'border bg-white dark:border-slate-800 dark:bg-slate-900' : 'bg-brand-600 text-white'}`}><p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>{assistant && <><CitationList citations={message.citations} /><div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-400">{message.provider && <span>{message.provider} · {message.model}</span>}<span title={message.request_id}>Request {message.request_id.slice(0, 8)}</span></div></>}</div></article>
}
