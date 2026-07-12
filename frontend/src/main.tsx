import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { App } from './App'
import { AuthProvider } from './features/auth/AuthProvider'
import './index.css'

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 15_000, retry: 1 }, mutations: { retry: false } } })
createRoot(document.getElementById('root')!).render(<StrictMode><QueryClientProvider client={queryClient}><BrowserRouter><AuthProvider><App /></AuthProvider></BrowserRouter></QueryClientProvider></StrictMode>)
