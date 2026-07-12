import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { conversationsApi } from '../api/endpoints'
import { useAuth } from '../features/auth/AuthProvider'

export function AppLayout() {
  const [open, setOpen] = useState(false)
  const { user, logout } = useAuth(); const navigate = useNavigate(); const client = useQueryClient()
  const conversations = useInfiniteQuery({ queryKey: ['conversations'], queryFn: ({ pageParam }) => conversationsApi.list(pageParam), initialPageParam: 0, getNextPageParam: (last) => last.offset + last.limit < last.total ? last.offset + last.limit : undefined })
  const conversationItems = conversations.data?.pages.flatMap((page) => page.items) || []
  const create = useMutation({ mutationFn: () => conversationsApi.create(), onSuccess: (value) => { void client.invalidateQueries({ queryKey: ['conversations'] }); navigate(`/chat/${value.id}`); setOpen(false) } })
  const linkClass = ({ isActive }: { isActive: boolean }) => `block rounded-lg px-3 py-2 text-sm ${isActive ? 'bg-brand-50 font-medium text-brand-700 dark:bg-slate-800 dark:text-brand-50' : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'}`
  return <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-white px-4 dark:border-slate-800 dark:bg-slate-900 lg:hidden">
      <button aria-label="Open navigation" onClick={() => setOpen(true)} className="rounded p-2">☰</button><Link to="/" className="font-semibold">KnowledgeHub AI</Link><span className="w-9" />
    </header>
    {open && <button aria-label="Close navigation" className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => setOpen(false)} />}
    <aside aria-label="Main navigation" className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r bg-white p-4 transition-transform dark:border-slate-800 dark:bg-slate-900 lg:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}>
      <div className="flex items-center justify-between"><Link to="/" className="text-lg font-bold">KnowledgeHub <span className="text-brand-600">AI</span></Link><button aria-label="Close navigation" className="lg:hidden" onClick={() => setOpen(false)}>×</button></div>
      <button onClick={() => create.mutate()} disabled={create.isPending} className="mt-6 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-medium text-white">＋ New conversation</button>
      <nav className="mt-5 space-y-1"><NavLink className={linkClass} to="/library" onClick={() => setOpen(false)}>Documents</NavLink><NavLink className={linkClass} to="/semantic-search" onClick={() => setOpen(false)}>Semantic search</NavLink></nav>
      <div className="mt-6 min-h-0 flex-1 overflow-y-auto"><p className="px-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Conversations</p><div className="mt-2 space-y-1">
        {conversationItems.map((item) => <NavLink key={item.id} className={linkClass} to={`/chat/${item.id}`} onClick={() => setOpen(false)}><span className="block truncate">{item.title}</span><span className="text-xs text-slate-400">{new Date(item.last_message_at).toLocaleDateString()}</span></NavLink>)}
        {conversations.hasNextPage && <button className="w-full px-3 py-2 text-left text-xs text-brand-600" onClick={() => conversations.fetchNextPage()}>Load more conversations</button>}
        {!conversations.isLoading && !conversationItems.length && <p className="px-3 py-4 text-sm text-slate-500">No conversations yet.</p>}
      </div></div>
      <div className="border-t pt-4 dark:border-slate-800"><p className="truncate text-sm font-medium">{user?.email}</p><div className="mt-3 flex gap-2"><button aria-label="Toggle color theme" className="rounded-lg border px-3 py-1.5 text-sm" onClick={() => document.documentElement.classList.toggle('dark')}>Theme</button><button className="rounded-lg border px-3 py-1.5 text-sm" onClick={() => { logout(); navigate('/login') }}>Logout</button></div></div>
    </aside>
    <main className="lg:pl-72"><Outlet /></main>
  </div>
}
