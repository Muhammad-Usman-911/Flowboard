// Pure functions that update a board's task list. They are used in two places:
//   1. optimistic drag-and-drop (update the screen before the server answers)
//   2. applying WebSocket events sent by the server
// They mirror the backend's ordering rules (backend/app/services/ordering.py):
// positions in every column are always 0..n-1 with no gaps.

import type { BoardEvent, Task } from '../api/types'

const byPosition = (a: Task, b: Task) => a.position - b.position || a.id - b.id

/** Tasks of one column, in display order. */
export function tasksInColumn(tasks: Task[], columnId: number): Task[] {
  return tasks.filter((t) => t.column_id === columnId).sort(byPosition)
}

/** Return a new list where `taskId` sits at `index` in `toColumnId`; both affected
 *  columns are renumbered 0..n-1. Unknown task ids leave the list unchanged. */
export function moveTaskLocally(tasks: Task[], taskId: number, toColumnId: number, index: number): Task[] {
  const task = tasks.find((t) => t.id === taskId)
  if (!task) return tasks
  const fromColumnId = task.column_id

  const target = tasksInColumn(tasks, toColumnId).filter((t) => t.id !== taskId)
  const clamped = Math.max(0, Math.min(index, target.length))
  target.splice(clamped, 0, { ...task, column_id: toColumnId })

  const updated = new Map<number, Task>()
  target.forEach((t, position) => updated.set(t.id, { ...t, position }))
  if (fromColumnId !== toColumnId) {
    tasksInColumn(tasks, fromColumnId)
      .filter((t) => t.id !== taskId)
      .forEach((t, position) => updated.set(t.id, { ...t, position }))
  }
  return tasks.map((t) => updated.get(t.id) ?? t)
}

/** Remove a task and close the gap it leaves in its column. */
export function removeTaskLocally(tasks: Task[], taskId: number): Task[] {
  const task = tasks.find((t) => t.id === taskId)
  if (!task) return tasks
  const rest = tasks.filter((t) => t.id !== taskId)
  const renumbered = new Map(tasksInColumn(rest, task.column_id).map((t, position) => [t.id, { ...t, position }]))
  return rest.map((t) => renumbered.get(t.id) ?? t)
}

/** Apply one WebSocket event to the task list. Returns the same array if nothing changed.
 *  Every branch is idempotent: applying an event twice gives the same result, so it does
 *  not matter that the user who made a change also receives its event. */
export function applyTaskEvent(tasks: Task[], event: BoardEvent): Task[] {
  switch (event.type) {
    case 'task.created': {
      const task = event.data as unknown as Task
      return tasks.some((t) => t.id === task.id) ? tasks.map((t) => (t.id === task.id ? task : t)) : [...tasks, task]
    }
    case 'task.updated': {
      const task = event.data as unknown as Task
      return tasks.map((t) => (t.id === task.id ? task : t))
    }
    case 'task.moved': {
      const task = event.data as unknown as Task
      const exists = tasks.some((t) => t.id === task.id)
      const base = exists ? tasks : [...tasks, task]
      const moved = moveTaskLocally(base, task.id, task.column_id, task.position)
      // Take the server's copy of the moved task (e.g. completed_at may have changed).
      return moved.map((t) => (t.id === task.id ? { ...task, position: t.position } : t))
    }
    case 'task.deleted':
      return removeTaskLocally(tasks, Number(event.data.id))
    default:
      return tasks
  }
}
