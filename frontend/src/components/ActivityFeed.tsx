import { useQuery } from '@tanstack/react-query'
import * as endpoints from '../api/endpoints'
import { timeAgo } from '../lib/format'
import { Avatar, Spinner } from './ui'

/** Recent activity for a workspace, a board or a single task. */
export function ActivityFeed({ workspaceId, boardId, taskId, limit = 15 }: { workspaceId: number; boardId?: number; taskId?: number; limit?: number }) {
  const params = { board_id: boardId, task_id: taskId, limit }
  const { data, isLoading } = useQuery({
    queryKey: ['activity', workspaceId, params],
    queryFn: () => endpoints.listActivity(workspaceId, params),
  })
  if (isLoading) return <Spinner small />
  if (!data?.items.length) return <p className="text-sm text-slate-500">No activity yet.</p>
  return (
    <ol className="space-y-3">
      {data.items.map((a) => (
        <li key={a.id} className="flex gap-2.5 text-sm">
          {a.user ? <Avatar user={a.user} size="sm" /> : <span className="h-6 w-6" />}
          <div className="min-w-0">
            <p className="text-slate-700 dark:text-slate-300">
              <span className="font-medium text-slate-900 dark:text-white">{a.user?.full_name || a.user?.username || 'Someone'}</span> {a.summary}
            </p>
            <p className="text-xs text-slate-500">{timeAgo(a.created_at)}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}
