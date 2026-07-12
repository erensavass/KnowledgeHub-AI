import { useQueryClient } from '@tanstack/react-query'
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { authApi } from '../../api/endpoints'
import { getAccessToken, setAccessToken } from '../../stores/auth-token'
import type { User } from '../../types/api'

type AuthContextValue = {
  user: User | null
  loading: boolean
  login(email: string, password: string): Promise<void>
  register(email: string, password: string): Promise<void>
  logout(): void
}
const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(Boolean(getAccessToken()))
  const queryClient = useQueryClient()

  useEffect(() => {
    const controller = new AbortController()
    const restore = async () => {
      if (!getAccessToken()) { setLoading(false); return }
      try { setUser(await authApi.me(controller.signal)) }
      catch { setAccessToken(null); setUser(null) }
      finally { setLoading(false) }
    }
    void restore()
    const unauthorized = () => { setUser(null); setLoading(false); queryClient.clear() }
    window.addEventListener('knowledgehub:unauthorized', unauthorized)
    return () => { controller.abort(); window.removeEventListener('knowledgehub:unauthorized', unauthorized) }
  }, [queryClient])

  async function authenticate(email: string, password: string, register: boolean) {
    if (register) await authApi.register({ email, password })
    const token = await authApi.login({ email, password })
    setAccessToken(token.access_token)
    setUser(await authApi.me())
  }
  const value = useMemo<AuthContextValue>(() => ({
    user, loading,
    login: (email, password) => authenticate(email, password, false),
    register: (email, password) => authenticate(email, password, true),
    logout: () => { setAccessToken(null); setUser(null); queryClient.clear() },
  // authenticate intentionally closes over current stable setters
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [user, loading, queryClient])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
