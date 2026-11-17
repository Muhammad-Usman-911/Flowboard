import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { errorMessage } from '../api/client'
import * as endpoints from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { Avatar, Button, Card, ErrorMessage, Field, Input } from '../components/ui'
import { timeAgo } from '../lib/format'
import { passwordProblem } from '../lib/validation'

export function ProfilePage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [fullName, setFullName] = useState(user?.full_name ?? '')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)
  const notifications = useQuery({ queryKey: ['notifications'], queryFn: () => endpoints.listNotifications() })

  const save = useMutation({
    mutationFn: (body: { full_name?: string; password?: string }) => endpoints.updateMe(body),
    onSuccess: (me) => {
      queryClient.setQueryData(['me'], me)
      setPassword('')
      setMessage('Saved.')
    },
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    setMessage(null)
    setLocalError(null)
    if (password) {
      const problem = passwordProblem(password)
      if (problem) return setLocalError(problem)
    }
    save.mutate({ full_name: fullName, ...(password ? { password } : {}) })
  }

  if (!user) return null
  return (
    <div className="mx-auto grid max-w-5xl gap-6 lg:grid-cols-2">
      <Card className="p-6">
        <div className="mb-6 flex items-center gap-4">
          <Avatar user={user} />
          <div>
            <h1 className="text-xl font-semibold">{user.full_name || user.username}</h1>
            <p className="text-sm text-slate-500">
              @{user.username} · {user.email}
            </p>
          </div>
        </div>
        <form onSubmit={onSubmit} className="space-y-4">
          <Field label="Full name">
            <Input value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </Field>
          <Field label="New password" hint="Leave empty to keep your current password.">
            <Input type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          {(localError || save.isError) && <ErrorMessage>{localError ?? errorMessage(save.error)}</ErrorMessage>}
          {message && <p className="text-sm text-emerald-600 dark:text-emerald-400">{message}</p>}
          <Button type="submit" loading={save.isPending}>
            Save changes
          </Button>
        </form>
      </Card>

      <Card className="p-6">
        <h2 className="mb-4 text-lg font-semibold">Notifications</h2>
        {notifications.data?.items.length === 0 && <p className="text-sm text-slate-500">Nothing yet. You'll be notified when someone @mentions or assigns you.</p>}
        <ul className="space-y-2">
          {notifications.data?.items.map((n) => (
            <li key={n.id} className={clsx('rounded-lg px-3 py-2 text-sm', !n.is_read && 'bg-indigo-50 dark:bg-indigo-950/40')}>
              {n.board_id ? (
                <Link className="hover:underline" to={`/boards/${n.board_id}${n.task_id ? `?task=${n.task_id}` : ''}`}>
                  {n.message}
                </Link>
              ) : (
                n.message
              )}
              <span className="block text-xs text-slate-500">{timeAgo(n.created_at)}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
