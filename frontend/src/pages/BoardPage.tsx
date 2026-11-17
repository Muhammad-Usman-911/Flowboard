// The Kanban board: columns of draggable task cards that update live.
//
// Drag-and-drop flow (see docs/LEARNING_GUIDE.md, "How a request flows"):
//   1. onDragEnd works out the target column + index
//   2. the cached task list is updated immediately (optimistic update)
//   3. POST /tasks/{id}/move is sent; on error the old list is put back
//   4. the server broadcasts "task.moved"; other browsers apply it in useBoardSocket

import {
  closestCorners,
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { errorMessage } from '../api/client'
import * as endpoints from '../api/endpoints'
import type { Task, TaskFilters } from '../api/types'
import { FilterBar } from '../components/board/FilterBar'
import { KanbanColumn } from '../components/board/KanbanColumn'
import { TaskCardView } from '../components/board/TaskCard'
import { TaskModal } from '../components/board/TaskModal'
import { ErrorMessage, FullPageSpinner } from '../components/ui'
import { useBoardSocket, type SocketStatus } from '../hooks/useBoardSocket'
import { moveTaskLocally, tasksInColumn } from '../lib/boardCache'
import { atLeast } from '../lib/format'
import { boardKeys } from '../lib/queryKeys'

const parseId = (id: string | number) => Number(String(id).split('-')[1])

function LiveIndicator({ status }: { status: SocketStatus }) {
  const text = { live: 'Live', connecting: 'Connecting…', offline: 'Offline, reconnecting…' }[status]
  return (
    <span className="flex items-center gap-1.5 text-xs font-medium text-slate-500 dark:text-slate-400" title="Real-time updates over WebSocket">
      <span className={clsx('h-2 w-2 rounded-full', status === 'live' ? 'bg-emerald-500' : status === 'connecting' ? 'bg-amber-400' : 'bg-red-500')} />
      {text}
    </span>
  )
}

export function BoardPage() {
  const boardId = Number(useParams().boardId)
  const [searchParams, setSearchParams] = useSearchParams()
  const openTaskId = searchParams.get('task') ? Number(searchParams.get('task')) : null
  const queryClient = useQueryClient()
  const [filters, setFilters] = useState<TaskFilters>({})
  const [activeTask, setActiveTask] = useState<Task | null>(null)
  const [overColumnId, setOverColumnId] = useState<number | null>(null)
  const status = useBoardSocket(boardId)

  const filtered = Object.keys(filters).length > 0
  const board = useQuery({ queryKey: boardKeys.board(boardId), queryFn: () => endpoints.getBoard(boardId) })
  const workspaceId = board.data?.workspace_id
  const workspace = useQuery({ queryKey: ['workspace', workspaceId], queryFn: () => endpoints.getWorkspace(workspaceId!), enabled: !!workspaceId })
  const members = useQuery({ queryKey: ['members', workspaceId], queryFn: () => endpoints.listMembers(workspaceId!), enabled: !!workspaceId })
  const tasksKey = filtered ? boardKeys.filteredTasks(boardId, filters) : boardKeys.allTasks(boardId)
  const tasks = useQuery({
    queryKey: tasksKey,
    queryFn: () => endpoints.listTasks(boardId, filters).then((page) => page.items),
    placeholderData: (previous) => previous, // keep showing old cards while a filter loads
  })

  const role = workspace.data?.my_role
  const canEdit = atLeast(role, 'member')
  const isAdmin = atLeast(role, 'admin')

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }), // a click is not a drag
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const move = useMutation({
    mutationFn: ({ taskId, columnId, index }: { taskId: number; columnId: number; index: number }) => endpoints.moveTask(taskId, columnId, index),
    onMutate: async ({ taskId, columnId, index }) => {
      // Optimistic update: change the cache now, remember the old value for rollback.
      const key = boardKeys.allTasks(boardId)
      await queryClient.cancelQueries({ queryKey: key })
      const previous = queryClient.getQueryData<Task[]>(key)
      queryClient.setQueryData<Task[]>(key, (old) => (old ? moveTaskLocally(old, taskId, columnId, index) : old))
      return { previous }
    },
    onError: (_error, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(boardKeys.allTasks(boardId), context.previous)
    },
  })

  const create = useMutation({
    mutationFn: ({ columnId, title }: { columnId: number; title: string }) => endpoints.createTask(boardId, { title, column_id: columnId }),
    onSuccess: (task) =>
      queryClient.setQueryData<Task[]>(boardKeys.allTasks(boardId), (old) => (old && !old.some((t) => t.id === task.id) ? [...old, task] : old)),
  })

  if (board.isLoading) return <FullPageSpinner />
  if (board.isError) return <ErrorMessage onRetry={() => board.refetch()}>{errorMessage(board.error)}</ErrorMessage>
  const detail = board.data!
  const allTasks = tasks.data ?? []

  const columnOf = (overId: string | number): number | null => {
    const id = String(overId)
    if (id.startsWith('column-')) return parseId(id)
    return allTasks.find((t) => t.id === parseId(id))?.column_id ?? null
  }

  function onDragStart(event: DragStartEvent) {
    setActiveTask(allTasks.find((t) => t.id === parseId(event.active.id)) ?? null)
  }

  function onDragOver(event: DragOverEvent) {
    setOverColumnId(event.over ? columnOf(event.over.id) : null)
  }

  function onDragEnd({ active, over }: DragEndEvent) {
    setActiveTask(null)
    setOverColumnId(null)
    if (!over) return
    const taskId = parseId(active.id)
    const task = allTasks.find((t) => t.id === taskId)
    const columnId = columnOf(over.id)
    if (!task || columnId === null) return

    const target = tasksInColumn(allTasks, columnId)
    const overId = String(over.id)
    // Dropped on a card: take that card's index. Dropped on the column: go to the end.
    const index = overId.startsWith('task-')
      ? target.findIndex((t) => t.id === parseId(overId))
      : target.filter((t) => t.id !== taskId).length
    if (columnId === task.column_id && index === task.position) return
    move.mutate({ taskId, columnId, index })
  }

  const openTask = (taskId: number) => setSearchParams({ task: String(taskId) })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="min-w-0">
          {workspace.data && (
            <Link to={`/workspaces/${workspace.data.id}`} className="text-sm text-slate-500 hover:underline">
              ← {workspace.data.name}
            </Link>
          )}
          <h1 className="text-2xl font-semibold">{detail.name}</h1>
        </div>
        <LiveIndicator status={status} />
        {workspaceId && (
          <Link to={`/workspaces/${workspaceId}/analytics?board=${boardId}`} className="ml-auto text-sm font-medium text-indigo-600 hover:underline dark:text-indigo-400">
            Board analytics →
          </Link>
        )}
      </div>

      <FilterBar filters={filters} onChange={setFilters} members={members.data?.items ?? []} labels={detail.labels} />
      {filtered && <p className="text-xs text-slate-500">Showing filtered tasks. Drag and drop is paused while filters are on.</p>}
      {!canEdit && role && <p className="text-xs text-slate-500">You are a viewer: the board is read-only.</p>}
      {tasks.isError && <ErrorMessage onRetry={() => tasks.refetch()}>{errorMessage(tasks.error)}</ErrorMessage>}
      {move.isError && <ErrorMessage>Could not move the task: {errorMessage(move.error)}</ErrorMessage>}

      <DndContext sensors={sensors} collisionDetection={closestCorners} onDragStart={onDragStart} onDragOver={onDragOver} onDragEnd={onDragEnd} onDragCancel={() => setActiveTask(null)}>
        <div className="-mx-4 flex gap-4 overflow-x-auto px-4 pb-4">
          {detail.columns.map((column) => (
            <KanbanColumn
              key={column.id}
              column={column}
              tasks={tasksInColumn(allTasks, column.id)}
              highlight={overColumnId === column.id && activeTask?.column_id !== column.id}
              canEdit={canEdit && !filtered}
              dragDisabled={!canEdit || filtered}
              onOpenTask={openTask}
              onAddTask={(columnId, title) => create.mutateAsync({ columnId, title })}
            />
          ))}
        </div>
        <DragOverlay>{activeTask && <TaskCardView task={activeTask} done={false} overlay />}</DragOverlay>
      </DndContext>

      {openTaskId && (
        <TaskModal
          key={openTaskId}
          taskId={openTaskId}
          board={detail}
          members={members.data?.items ?? []}
          canEdit={canEdit}
          isAdmin={isAdmin}
          onClose={() => setSearchParams({})}
        />
      )}
    </div>
  )
}
