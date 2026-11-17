import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { errorMessage } from '../api/client'
import * as endpoints from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { Button, ErrorMessage, Field, Input } from '../components/ui'
import { passwordProblem } from '../lib/validation'
import { AuthShell } from './AuthShell'

export function RegisterPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email: '', username: '', full_name: '', password: '' })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [key]: e.target.value })

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const problem = passwordProblem(form.password)
    if (problem) return setError(problem)
    setBusy(true)
    setError(null)
    try {
      await endpoints.register(form)
      await login(form.email, form.password)
      navigate('/workspaces', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title="Create your account" subtitle="Start organising work with your team.">
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Field label="Full name">
          <Input value={form.full_name} onChange={set('full_name')} autoComplete="name" />
        </Field>
        <Field label="Username" hint="3-32 letters, digits or underscores. Teammates @mention you with it.">
          <Input value={form.username} onChange={set('username')} autoComplete="username" required />
        </Field>
        <Field label="Email">
          <Input type="email" value={form.email} onChange={set('email')} autoComplete="email" required />
        </Field>
        <Field label="Password" hint="At least 8 characters, with a letter and a digit.">
          <Input type="password" value={form.password} onChange={set('password')} autoComplete="new-password" required />
        </Field>
        {error && <ErrorMessage>{error}</ErrorMessage>}
        <Button type="submit" className="w-full" loading={busy}>
          Create account
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-slate-500">
        Already registered?{' '}
        <Link to="/login" className="font-medium text-indigo-600 hover:underline dark:text-indigo-400">
          Log in
        </Link>
      </p>
    </AuthShell>
  )
}
