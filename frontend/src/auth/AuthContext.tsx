// Who is logged in? The AuthProvider answers that for the whole app.
// The user object itself is just a TanStack Query (['me']), so it is cached and
// refetched like any other server data.

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, type ReactNode } from 'react'
import { useNavigate } from 'react-router'
import { setAuthFailureHandler } from '../api/client'
import * as endpoints from '../api/endpoints'
import { tokenStore } from '../api/tokens'
import type { UserMe } from '../api/types'

interface AuthState {
  user: UserMe | undefined
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const me = useQuery({
    queryKey: ['me'],
    queryFn: endpoints.getMe,
    enabled: !!tokenStore.access,
    retry: false,
    staleTime: 5 * 60_000,
  })

  const logout = useCallback(() => {
    tokenStore.clear()
    queryClient.clear()
    navigate('/login')
  }, [navigate, queryClient])

  useEffect(() => setAuthFailureHandler(logout), [logout])

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await endpoints.login(email, password)
      tokenStore.set(tokens.access_token, tokens.refresh_token)
      await queryClient.fetchQuery({ queryKey: ['me'], queryFn: endpoints.getMe })
    },
    [queryClient],
  )

  const value = useMemo<AuthState>(
    () => ({ user: me.data, isLoading: !!tokenStore.access && me.isLoading, login, logout }),
    [me.data, me.isLoading, login, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
