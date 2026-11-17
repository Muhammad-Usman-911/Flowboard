import { Navigate, Outlet, useLocation } from 'react-router'
import { tokenStore } from '../api/tokens'
import { FullPageSpinner } from '../components/ui'
import { useAuth } from './AuthContext'

/** Wrap routes that need a logged-in user. Others are sent to /login (and come back). */
export function ProtectedRoute() {
  const { user, isLoading } = useAuth()
  const location = useLocation()
  if (isLoading) return <FullPageSpinner />
  if (!user || !tokenStore.access) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  return <Outlet />
}
