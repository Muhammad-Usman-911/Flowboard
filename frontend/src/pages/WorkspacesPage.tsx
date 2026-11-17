import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { errorMessage } from '../api/client'
import * as endpoints from '../api/endpoints'
import { Button, Card, EmptyState, ErrorMessage, FullPageSpinner, Input, RoleBadge } from '../components/ui'

export function WorkspacesPage() {
  const queryClient = useQueryClient()
  const workspaces = useQuery({ queryKey: ['workspaces'], queryFn: endpoints.listWorkspaces })
  const [name, setName] = useState('')
  const create = useMutation({
    mutationFn: () => endpoints.createWorkspace({ name }),
    onSuccess: () => {
      setName('')
      queryClient.invalidateQueries({ queryKey: ['workspaces'] })
    },
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (name.trim()) create.mutate()
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Workspaces</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">Each workspace has its own members, roles and boards.</p>
        </div>
        <form onSubmit={onSubmit} className="flex w-full gap-2 sm:w-auto">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="New workspace name" aria-label="New workspace name" className="sm:w-64" />
          <Button type="submit" loading={create.isPending} disabled={!name.trim()}>
            Create
          </Button>
        </form>
      </div>
      {create.isError && <ErrorMessage>{errorMessage(create.error)}</ErrorMessage>}

      {workspaces.isLoading && <FullPageSpinner />}
      {workspaces.isError && <ErrorMessage onRetry={() => workspaces.refetch()}>{errorMessage(workspaces.error)}</ErrorMessage>}
      {workspaces.data?.items.length === 0 && <EmptyState title="No workspaces yet">Create one above, or ask a teammate to invite you.</EmptyState>}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {workspaces.data?.items.map((ws) => (
          <Link key={ws.id} to={`/workspaces/${ws.id}`} className="group">
            <Card className="h-full p-5 transition group-hover:-translate-y-0.5 group-hover:border-indigo-300 group-hover:shadow-md dark:group-hover:border-indigo-700">
              <div className="flex items-start justify-between gap-3">
                <h2 className="font-semibold">{ws.name}</h2>
                <RoleBadge role={ws.my_role} />
              </div>
              <p className="mt-2 line-clamp-2 text-sm text-slate-500 dark:text-slate-400">{ws.description || 'No description'}</p>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  )
}
