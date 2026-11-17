// The axios instance every API call goes through.
//
// 1. A *request* interceptor adds `Authorization: Bearer <access token>`.
// 2. A *response* interceptor catches 401s: it uses the refresh token to get a new
//    token pair, then retries the original request once. If many requests fail at
//    the same time, they all wait for ONE refresh call (the `refreshing` promise).
// 3. If the refresh itself fails, tokens are cleared and `onAuthFailure` runs (the
//    AuthProvider sends the user to /login).

import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { tokenStore } from './tokens'
import type { ApiErrorBody, TokenPair } from './types'

export const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1'

export const api = axios.create({ baseURL: API_BASE })

let refreshing: Promise<string> | null = null
let onAuthFailure: () => void = () => {}

export function setAuthFailureHandler(handler: () => void) {
  onAuthFailure = handler
}

/** Get a new token pair. Concurrent callers share the same in-flight request. */
export function refreshTokens(): Promise<string> {
  if (!refreshing) {
    const refreshToken = tokenStore.refresh
    refreshing = (
      refreshToken
        ? axios
            // A plain axios call (not `api`) so this request is never intercepted itself.
            .post<TokenPair>(`${API_BASE}/auth/refresh`, { refresh_token: refreshToken }, {
              adapter: api.defaults.adapter,
            })
            .then((res) => {
              tokenStore.set(res.data.access_token, res.data.refresh_token)
              return res.data.access_token
            })
        : Promise.reject(new Error('No refresh token'))
    ).finally(() => {
      refreshing = null
    })
  }
  return refreshing
}

api.interceptors.request.use((config) => {
  const token = tokenStore.access
  if (token) config.headers.set('Authorization', `Bearer ${token}`)
  return config
})

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean }

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiErrorBody>) => {
    const original = error.config as RetriableConfig | undefined
    const isAuthCall = original?.url?.includes('/auth/')
    if (error.response?.status !== 401 || !original || original._retried || isAuthCall) {
      throw error
    }
    original._retried = true
    try {
      const token = await refreshTokens()
      original.headers.set('Authorization', `Bearer ${token}`)
      return api(original)
    } catch {
      tokenStore.clear()
      onAuthFailure()
      throw error
    }
  },
)

/** A readable message for any error thrown by an API call. */
export function errorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    if (error.response?.data?.detail) return error.response.data.detail
    if (!error.response) return 'Cannot reach the server. Is the API running?'
  }
  return error instanceof Error ? error.message : 'Something went wrong'
}
