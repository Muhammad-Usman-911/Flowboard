import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import { errorMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Button, ErrorMessage, Field, Input } from '../components/ui'
import { AuthShell } from './AuthShell'

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/workspaces'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to={from} replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!email || !password) {
      setError('Enter your email and password.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title="Welcome back" subtitle="Log in to your Flowboard account.">
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Field label="Email">
          <Input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="owner@flowboard.dev" />
        </Field>
        <Field label="Password">
          <Input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
        </Field>
        {error && <ErrorMessage>{error}</ErrorMessage>}
        <Button type="submit" className="w-full" loading={busy}>
          Log in
        </Button>
      </form>
      <p className="mt-4 rounded-lg bg-slate-50 p-3 text-xs text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
        Demo: <code>owner@flowboard.dev</code> / <code>Password123</code> (after running the seed)
      </p>
      <p className="mt-4 text-center text-sm text-slate-500">
        No account?{' '}
        <Link to="/register" className="font-medium text-indigo-600 hover:underline dark:text-indigo-400">
          Create one
        </Link>
      </p>
    </AuthShell>
  )
}
