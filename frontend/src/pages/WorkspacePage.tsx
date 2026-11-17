import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'
import { errorMessage } from '../api/client'
import * as endpoints from '../api/endpoints'
import type { Role } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { ActivityFeed } from '../components/ActivityFeed'
import { Avatar, Button, Card, EmptyState, ErrorMessage, FullPageSpinner, Input, RoleBadge, Select } from '../components/ui'
import { atLeast } from '../lib/format'

export function WorkspacePage() {
  const workspaceId = Number(useParams().workspaceId)
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const workspace = useQuery({ queryKey: ['workspace', workspaceId], queryFn: () => endpoints.getWorkspace(workspaceId) })
  const boards = useQuery({ queryKey: ['boards', workspaceId], queryFn: () => endpoints.listBoards(workspaceId) })
  const members = useQuery({ queryKey: ['members', workspaceId], queryFn: () => endpoints.listMembers(workspaceId) })

  const [boardName, setBoardName] = useState('')
  const [invite, setInvite] = useState<{ email: string; role: Role }>({ email: '', role: 'member' })

  const myRole = workspace.data?.my_role
  const isAdmin = atLeast(myRole, 'admin')

  const createBoard = useMutation({
    mutationFn: () => endpoints.createBoard(workspaceId, { name: boardName }),
    onSuccess: () => {
      setBoardName('')
      queryClient.invalidateQueries({ queryKey: ['boards', workspaceId] })
    },
  })
  const inviteMember = useMutation({
    mutationFn: () => endpoints.inviteMember(workspaceId, invite.email, invite.role),
    onSuccess: () => {
      setInvite({ email: '', role: 'member' })
      queryClient.invalidateQueries({ queryKey: ['members', workspaceId] })
    },
  })
  const membersChanged = () => queryClient.invalidateQueries({ queryKey: ['members', workspaceId] })
  const changeRole = useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: Role }) => endpoints.changeMemberRole(workspaceId, userId, role),
    onSettled: membersChanged,
  })
  const remove = useMutation({ mutationFn: (userId: number) => endpoints.removeMember(workspaceId, userId), onSettled: membersChanged })

  if (workspace.isLoading) return <FullPageSpinner />
  if (workspace.isError) return <ErrorMessage onRetry={() => workspace.refetch()}>{errorMessage(workspace.error)}</ErrorMessage>
  const ws = workspace.data!

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link to="/workspaces" className="text-sm text-slate-500 hover:underline">
            ← Workspaces
          </Link>
          <h1 className="mt-1 flex items-center gap-3 text-2xl font-semibold">
            {ws.name} <RoleBadge role={ws.my_role} />
          </h1>
          {ws.description && <p className="mt-1 max-w-2xl text-sm text-slate-500 dark:text-slate-400">{ws.description}</p>}
        </div>
        <Link to={`/workspaces/${workspaceId}/analytics`}>
          <Button variant="secondary">View analytics</Button>
        </Link>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <section className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold">Boards</h2>
            {isAdmin && (
              <form
                className="flex w-full gap-2 sm:w-auto"
                onSubmit={(e: FormEvent) => {
                  e.preventDefault()
                  if (boardName.trim()) createBoard.mutate()
                }}
              >
                <Input value={boardName} onChange={(e) => setBoardName(e.target.value)} placeholder="New board name" aria-label="New board name" className="sm:w-56" />
                <Button type="submit" loading={createBoard.isPending} disabled={!boardName.trim()}>
                  Add board
                </Button>
              </form>
            )}
          </div>
          {createBoard.isError && <ErrorMessage>{errorMessage(createBoard.error)}</ErrorMessage>}
          {boards.isLoading && <FullPageSpinner />}
          {boards.data?.items.length === 0 && <EmptyState title="No boards yet">{isAdmin ? 'Create the first one above.' : 'An admin can create one.'}</EmptyState>}
          <div className="grid gap-4 sm:grid-cols-2">
            {boards.data?.items.map((b) => (
              <Link key={b.id} to={`/boards/${b.id}`} className="group">
                <Card className="h-full p-5 transition group-hover:-translate-y-0.5 group-hover:border-indigo-300 group-hover:shadow-md dark:group-hover:border-indigo-700">
                  <h3 className="font-semibold">{b.name}</h3>
                  <p className="mt-1 line-clamp-2 text-sm text-slate-500 dark:text-slate-400">{b.description || 'No description'}</p>
                </Card>
              </Link>
            ))}
          </div>

          <h2 className="pt-4 text-lg font-semibold">Members</h2>
          <Card className="divide-y divide-slate-100 dark:divide-slate-700/60">
            {members.data?.items.map((m) => {
              const canManage = isAdmin && m.role !== 'owner' && (myRole === 'owner' || m.role !== 'admin')
              const isMe = m.user.id === user?.id
              return (
                <div key={m.user.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                  <Avatar user={m.user} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {m.user.full_name || m.user.username} {isMe && <span className="text-slate-400">(you)</span>}
                    </p>
                    <p className="text-xs text-slate-500">@{m.user.username}</p>
                  </div>
                  {canManage && !isMe ? (
                    <>
                      <Select
                        aria-label={`Role of ${m.user.username}`}
                        className="w-28"
                        value={m.role}
                        onChange={(e) => changeRole.mutate({ userId: m.user.id, role: e.target.value as Role })}
                      >
                        {myRole === 'owner' && <option value="admin">Admin</option>}
                        <option value="member">Member</option>
                        <option value="viewer">Viewer</option>
                      </Select>
                      <Button variant="ghost" onClick={() => confirm(`Remove @${m.user.username}?`) && remove.mutate(m.user.id)}>
                        Remove
                      </Button>
                    </>
                  ) : (
                    <RoleBadge role={m.role} />
                  )}
                </div>
              )
            })}
            {isAdmin && (
              <form
                className="flex flex-wrap gap-2 px-4 py-3"
                onSubmit={(e: FormEvent) => {
                  e.preventDefault()
                  if (invite.email) inviteMember.mutate()
                }}
              >
                <Input
                  type="email"
                  className="min-w-0 flex-1"
                  placeholder="teammate@example.com"
                  aria-label="Email to invite"
                  value={invite.email}
                  onChange={(e) => setInvite({ ...invite, email: e.target.value })}
                />
                <Select className="w-28" aria-label="Role" value={invite.role} onChange={(e) => setInvite({ ...invite, role: e.target.value as Role })}>
                  {myRole === 'owner' && <option value="admin">Admin</option>}
                  <option value="member">Member</option>
                  <option value="viewer">Viewer</option>
                </Select>
                <Button type="submit" loading={inviteMember.isPending}>
                  Invite
                </Button>
              </form>
            )}
          </Card>
          {[inviteMember, changeRole, remove].map((m, i) => m.isError && <ErrorMessage key={i}>{errorMessage(m.error)}</ErrorMessage>)}
        </section>

        <aside>
          <Card className="p-4">
            <h2 className="mb-4 font-semibold">Recent activity</h2>
            <ActivityFeed workspaceId={workspaceId} />
          </Card>
        </aside>
      </div>
    </div>
  )
}
