import { useDroppable } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import clsx from 'clsx'
import { useState, type FormEvent } from 'react'
import type { Column, Task } from '../../api/types'
import { Input } from '../ui'
import { SortableTaskCard } from './TaskCard'

interface Props {
  column: Column
  tasks: Task[]
  highlight: boolean
  canEdit: boolean
  dragDisabled: boolean
  onOpenTask: (taskId: number) => void
  onAddTask: (columnId: number, title: string) => Promise<unknown>
}

export function KanbanColumn({ column, tasks, highlight, canEdit, dragDisabled, onOpenTask, onAddTask }: Props) {
  // The column itself is a drop target, so tasks can be dropped into an empty column.
  const { setNodeRef } = useDroppable({ id: `column-${column.id}`, data: { columnId: column.id } })
  const [adding, setAdding] = useState(false)
  const [title, setTitle] = useState('')

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!title.trim()) return
    await onAddTask(column.id, title.trim())
    setTitle('')
  }

  return (
    <section
      aria-label={column.title}
      className={clsx(
        'flex max-h-[calc(100vh-14rem)] w-72 shrink-0 flex-col rounded-xl border bg-slate-100/80 transition dark:bg-slate-900/70',
        highlight ? 'border-indigo-400 dark:border-indigo-500' : 'border-transparent dark:border-slate-800',
      )}
    >
      <header className="flex items-center gap-2 px-3 pt-3 pb-2">
        <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">{column.title}</h2>
        <span className="rounded-full bg-slate-200 px-2 text-xs font-medium text-slate-600 dark:bg-slate-700 dark:text-slate-300">{tasks.length}</span>
        {column.is_done && <span className="ml-auto text-xs font-medium text-emerald-600 dark:text-emerald-400">✓ Done</span>}
      </header>
      <div ref={setNodeRef} className="flex min-h-16 flex-1 flex-col gap-2 overflow-y-auto px-2 pb-2">
        <SortableContext items={tasks.map((t) => `task-${t.id}`)} strategy={verticalListSortingStrategy}>
          {tasks.map((task) => (
            <SortableTaskCard key={task.id} task={task} done={column.is_done} disabled={dragDisabled} onOpen={() => onOpenTask(task.id)} />
          ))}
        </SortableContext>
      </div>
      {canEdit && (
        <div className="px-2 pb-2">
          {adding ? (
            <form onSubmit={submit}>
              <Input
                autoFocus
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                onBlur={() => !title && setAdding(false)}
                onKeyDown={(e) => e.key === 'Escape' && setAdding(false)}
                placeholder="Task title, then Enter"
                aria-label={`New task in ${column.title}`}
              />
            </form>
          ) : (
            <button
              onClick={() => setAdding(true)}
              className="w-full rounded-lg px-2 py-1.5 text-left text-sm text-slate-500 hover:bg-slate-200/70 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            >
              + Add task
            </button>
          )}
        </div>
      )}
    </section>
  )
}
