import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../features/auth/AuthProvider'

export function ProtectedRoute() {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <div className="grid min-h-screen place-items-center" role="status">Restoring your session…</div>
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <Outlet />
}
