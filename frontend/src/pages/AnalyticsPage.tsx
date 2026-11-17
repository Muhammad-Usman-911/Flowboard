import { useQuery } from '@tanstack/react-query'
import { Link, useParams, useSearchParams } from 'react-router'
import { errorMessage } from '../api/client'
import * as endpoints from '../api/endpoints'
import { Avatar, Card, EmptyState, ErrorMessage, FullPageSpinner, Select } from '../components/ui'
import { formatDate } from '../lib/format'

/** A headline number. */
function Stat({ label, value, note }: { label: string; value: string | number; note?: string }) {
  return (
    <Card className="p-4">
      <p className="text-sm text-slate-500 dark:text-slate-400">{label}</p>
      <p className="mt-1 text-3xl font-semibold tabular-nums">{value}</p>
      {note && <p className="mt-1 text-xs text-slate-500">{note}</p>}
    </Card>
  )
}

/** Horizontal bar: one hue, value label in text color (not the bar color). */
function HBar({ label, value, max, display }: { label: React.ReactNode; value: number; max: number; display: string }) {
  const pct = max > 0 ? (value / max) * 100 : 0
  return (
    <div className="grid grid-cols-[minmax(0,9rem)_1fr_3.5rem] items-center gap-3 text-sm" title={`${typeof label === 'string' ? label : ''} ${display}`}>
      <div className="truncate text-slate-600 dark:text-slate-300">{label}</div>
      <div className="h-3 rounded-r bg-slate-100 dark:bg-slate-800">
        <div className="h-3 rounded-r bg-indigo-500 dark:bg-indigo-400" style={{ width: `${Math.max(pct, value > 0 ? 2 : 0)}%` }} />
      </div>
      <div className="text-right font-medium tabular-nums text-slate-700 dark:text-slate-200">{display}</div>
    </div>
  )
}

export function AnalyticsPage() {
  const workspaceId = Number(useParams().workspaceId)
  const [params, setParams] = useSearchParams()
  const boardId = params.get('board') ? Number(params.get('board')) : undefined

  const workspace = useQuery({ queryKey: ['workspace', workspaceId], queryFn: () => endpoints.getWorkspace(workspaceId) })
  const boards = useQuery({ queryKey: ['boards', workspaceId], queryFn: () => endpoints.listBoards(workspaceId) })
  const analytics = useQuery({ queryKey: ['analytics', workspaceId, boardId], queryFn: () => endpoints.getAnalytics(workspaceId, boardId) })

  const data = analytics.data
  const statusMax = Math.max(1, ...(data?.tasks_per_status.map((s) => s.count) ?? []))
  const weekMax = Math.max(1, ...(data?.tasks_created_per_week.map((w) => w.count) ?? []))
  const completion = data && data.total_tasks ? Math.round((data.completed_tasks / data.total_tasks) * 100) : 0

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link to={`/workspaces/${workspaceId}`} className="text-sm text-slate-500 hover:underline">
            ← {workspace.data?.name ?? 'Workspace'}
          </Link>
          <h1 className="mt-1 text-2xl font-semibold">Analytics</h1>
        </div>
        <Select
          aria-label="Board"
          className="w-56"
          value={boardId ?? ''}
          onChange={(e) => setParams(e.target.value ? { board: e.target.value } : {})}
        >
          <option value="">All boards</option>
          {boards.data?.items.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </Select>
      </div>

      {analytics.isLoading && <FullPageSpinner />}
      {analytics.isError && <ErrorMessage onRetry={() => analytics.refetch()}>{errorMessage(analytics.error)}</ErrorMessage>}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Stat label="Total tasks" value={data.total_tasks} />
            <Stat label="Completed" value={data.completed_tasks} note="in a column marked Done" />
            <Stat label="Completion" value={`${completion}%`} />
            <Stat label="Overdue" value={data.overdue_tasks} note="past due, not done" />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card className="p-5">
              <h2 className="mb-4 font-semibold">Tasks per status</h2>
              <div className="space-y-3">
                {data.tasks_per_status.map((s) => (
                  <HBar key={s.title} label={s.title + (s.is_done ? ' ✓' : '')} value={s.count} max={statusMax} display={String(s.count)} />
                ))}
              </div>
            </Card>

            <Card className="p-5">
              <h2 className="mb-4 font-semibold">Completion rate per member</h2>
              {data.completion_by_member.length === 0 ? (
                <EmptyState title="No assigned tasks yet" />
              ) : (
                <div className="space-y-3">
                  {data.completion_by_member.map((m) => (
                    <HBar
                      key={m.user.id}
                      label={
                        <span className="flex items-center gap-2">
                          <Avatar user={m.user} size="sm" />
                          <span className="truncate">{m.user.full_name || m.user.username}</span>
                        </span>
                      }
                      value={m.completion_rate}
                      max={1}
                      display={`${Math.round(m.completion_rate * 100)}%`}
                    />
                  ))}
                  <p className="pt-1 text-xs text-slate-500">Completed / assigned tasks.</p>
                </div>
              )}
            </Card>
          </div>

          <Card className="p-5">
            <h2 className="mb-4 font-semibold">Tasks created per week</h2>
            <div className="flex h-48 items-end gap-2 border-b border-slate-200 dark:border-slate-700" role="img" aria-label="Tasks created per week">
              {data.tasks_created_per_week.map((w) => (
                <div key={w.week_start} className="group relative flex h-full flex-1 flex-col items-center justify-end">
                  <span className="mb-1 text-xs font-medium tabular-nums text-slate-600 dark:text-slate-300">{w.count || ''}</span>
                  <div
                    className="w-full max-w-10 rounded-t bg-indigo-500 transition group-hover:bg-indigo-600 dark:bg-indigo-400 dark:group-hover:bg-indigo-300"
                    style={{ height: `${(w.count / weekMax) * 85}%` }}
                    title={`Week of ${formatDate(w.week_start)}: ${w.count} tasks`}
                  />
                </div>
              ))}
            </div>
            <div className="mt-2 flex gap-2">
              {data.tasks_created_per_week.map((w) => (
                <span key={w.week_start} className="flex-1 text-center text-[11px] text-slate-500">
                  {formatDate(w.week_start)}
                </span>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
