// Tests the automatic token refresh in api/client.ts with a fake axios adapter
// (no real network): the adapter plays the role of the server.

import type { AxiosAdapter, InternalAxiosRequestConfig } from 'axios'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, errorMessage, setAuthFailureHandler } from '../client'
import { tokenStore } from '../tokens'

function respond(config: InternalAxiosRequestConfig, status: number, data: unknown) {
  const response = { data, status, statusText: String(status), headers: {}, config }
  if (status >= 400) {
    return Promise.reject(Object.assign(new Error(`HTTP ${status}`), { isAxiosError: true, response, config }))
  }
  return Promise.resolve(response)
}

const originalAdapter = api.defaults.adapter
afterEach(() => {
  api.defaults.adapter = originalAdapter
})

describe('api client', () => {
  it('refreshes an expired access token once and retries every failed request', async () => {
    tokenStore.set('old-access', 'refresh-1')
    let refreshCalls = 0
    const fakeServer: AxiosAdapter = (config) => {
      if (config.url?.endsWith('/auth/refresh')) {
        refreshCalls += 1
        return respond(config, 200, { access_token: 'new-access', refresh_token: 'refresh-2' })
      }
      const auth = config.headers.get('Authorization')
      return auth === 'Bearer new-access' ? respond(config, 200, { ok: true }) : respond(config, 401, { detail: 'expired', code: 'token_expired' })
    }
    api.defaults.adapter = fakeServer

    const [a, b] = await Promise.all([api.get('/users/me'), api.get('/workspaces')])
    expect(a.data).toEqual({ ok: true })
    expect(b.data).toEqual({ ok: true })
    expect(refreshCalls).toBe(1) // two 401s, but only ONE refresh request
    expect(tokenStore.access).toBe('new-access')
    expect(tokenStore.refresh).toBe('refresh-2')
  })

  it('logs out when the refresh token is rejected too', async () => {
    tokenStore.set('old-access', 'bad-refresh')
    const onFailure = vi.fn()
    setAuthFailureHandler(onFailure)
    api.defaults.adapter = (config) => respond(config, 401, { detail: 'Invalid token', code: 'invalid_token' })

    await expect(api.get('/users/me')).rejects.toThrow()
    expect(onFailure).toHaveBeenCalledOnce()
    expect(tokenStore.access).toBeNull()
  })

  it('turns API errors into readable messages', async () => {
    api.defaults.adapter = (config) => respond(config, 409, { detail: 'This username is taken', code: 'username_taken' })
    const error = await api.post('/auth/register', {}).catch((e: unknown) => e)
    expect(errorMessage(error)).toBe('This username is taken')
    expect(errorMessage(new Error('boom'))).toBe('boom')
  })
})
