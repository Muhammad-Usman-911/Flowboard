import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import clsx from 'clsx'
import type { Task } from '../../api/types'
import { formatDate, isOverdue } from '../../lib/format'
import { Avatar, PriorityBadge } from '../ui'

interface CardProps {
  task: Task
  done: boolean
  onOpen?: () => void
  overlay?: boolean
}

/** The visual card (also used inside the DragOverlay while dragging). */
export function TaskCardView({ task, done, onOpen, overlay }: CardProps) {
  const overdue = isOverdue(task.due_date, done)
  return (
    <div
      onClick={onOpen}
      className={clsx(
        'group cursor-pointer rounded-lg border bg-white p-3 text-left shadow-sm transition hover:border-indigo-300 dark:bg-slate-800 dark:hover:border-indigo-600',
        'border-slate-200 dark:border-slate-700',
        overlay && 'rotate-2 shadow-xl ring-2 ring-indigo-500',
      )}
    >
      {task.labels.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1">
          {task.labels.map((l) => (
            <span key={l.id} className="rounded px-1.5 py-0.5 text-[10px] font-semibold text-white" style={{ backgroundColor: l.color }}>
              {l.name}
            </span>
          ))}
        </div>
      )}
      <p className={clsx('text-sm font-medium text-slate-800 dark:text-slate-100', done && 'text-slate-500 line-through dark:text-slate-400')}>{task.title}</p>
      <div className="mt-2.5 flex items-center gap-2">
        <PriorityBadge priority={task.priority} />
        {task.due_date && (
          <span
            className={clsx(
              'text-xs',
              overdue ? 'font-semibold text-red-600 dark:text-red-400' : 'text-slate-500 dark:text-slate-400',
            )}
            title={overdue ? 'Overdue' : 'Due date'}
          >
            {overdue ? 'Overdue · ' : ''}
            {formatDate(task.due_date)}
          </span>
        )}
        <span className="ml-auto">{task.assignee && <Avatar user={task.assignee} size="sm" />}</span>
      </div>
    </div>
  )
}

/** A card that can be dragged and sorted (dnd-kit). */
export function SortableTaskCard({ task, done, onOpen, disabled }: CardProps & { disabled: boolean }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: `task-${task.id}`,
    data: { columnId: task.column_id },
    disabled,
  })
  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Translate.toString(transform), transition }}
      className={clsx(isDragging && 'opacity-40')}
      data-testid={`task-${task.id}`}
      {...attributes}
      {...listeners}
    >
      <TaskCardView task={task} done={done} onOpen={onOpen} />
    </div>
  )
}
