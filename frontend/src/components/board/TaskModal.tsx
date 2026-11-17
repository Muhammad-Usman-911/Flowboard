// The task detail modal: edit fields, comments (with @mentions), attachments, history.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { errorMessage } from '../../api/client'
import * as endpoints from '../../api/endpoints'
import type { BoardDetail, Member, Priority, Task } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { formatBytes, PRIORITIES, timeAgo } from '../../lib/format'
import { boardKeys } from '../../lib/queryKeys'
import { ActivityFeed } from '../ActivityFeed'
import { Avatar, Button, ErrorMessage, Field, FullPageSpinner, Input, Modal, Select, Textarea } from '../ui'

interface Props {
  taskId: number
  board: BoardDetail
  members: Member[]
  canEdit: boolean
  isAdmin: boolean
  onClose: () => void
}

/** Highlight @mentions in a comment body. */
function CommentBody({ body }: { body: string }) {
  return (
    <p className="text-sm whitespace-pre-wrap text-slate-700 dark:text-slate-300">
      {body.split(/(@[a-zA-Z0-9_]{3,32})/g).map((part, i) =>
        part.startsWith('@') ? (
          <span key={i} className="font-medium text-indigo-600 dark:text-indigo-400">
            {part}
          </span>
        ) : (
          part
        ),
      )}
    </p>
  )
}

export function TaskModal({ taskId, board, members, canEdit, isAdmin, onClose }: Props) {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const fileInput = useRef<HTMLInputElement>(null)

  const cachedTask = queryClient.getQueryData<Task[]>(boardKeys.allTasks(board.id))?.find((t) => t.id === taskId)
  const task = useQuery({ queryKey: ['task', taskId], queryFn: () => endpoints.getTask(taskId), initialData: cachedTask })
  const comments = useQuery({ queryKey: ['comments', taskId], queryFn: () => endpoints.listComments(taskId) })
  const attachments = useQuery({ queryKey: ['attachments', taskId], queryFn: () => endpoints.listAttachments(taskId) })

  const [title, setTitle] = useState(task.data?.title ?? '')
  const [description, setDescription] = useState(task.data?.description ?? '')
  const [comment, setComment] = useState('')
  useEffect(() => {
    setTitle(task.data?.title ?? '')
    setDescription(task.data?.description ?? '')
  }, [task.data?.title, task.data?.description])

  /** After any change: put the server's copy in the caches (the WebSocket echo is harmless). */
  const saved = (updated: Task) => {
    queryClient.setQueryData(['task', taskId], updated)
    queryClient.setQueryData<Task[]>(boardKeys.allTasks(board.id), (old) => old?.map((t) => (t.id === updated.id ? updated : t)))
    queryClient.invalidateQueries({ queryKey: boardKeys.filteredTasks(board.id) })
    queryClient.invalidateQueries({ queryKey: ['activity'] })
  }
  const update = useMutation({ mutationFn: (body: endpoints.TaskInput) => endpoints.updateTask(taskId, body), onSuccess: saved })
  const move = useMutation({ mutationFn: (columnId: number) => endpoints.moveTask(taskId, columnId, 0), onSuccess: saved })
  const remove = useMutation({
    mutationFn: () => endpoints.deleteTask(taskId),
    onSuccess: () => {
      queryClient.setQueryData<Task[]>(boardKeys.allTasks(board.id), (old) => old?.filter((t) => t.id !== taskId))
      onClose()
    },
  })
  const addComment = useMutation({
    mutationFn: () => endpoints.addComment(taskId, comment),
    onSuccess: () => {
      setComment('')
      queryClient.invalidateQueries({ queryKey: ['comments', taskId] })
      queryClient.invalidateQueries({ queryKey: ['activity'] })
    },
  })
  const deleteComment = useMutation({
    mutationFn: endpoints.deleteComment,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['comments', taskId] }),
  })
  const upload = useMutation({
    mutationFn: (file: File) => endpoints.uploadAttachment(taskId, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['attachments', taskId] }),
  })
  const removeAttachment = useMutation({
    mutationFn: endpoints.deleteAttachment,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['attachments', taskId] }),
  })

  const t = task.data
  const error = [update, move, remove, addComment, deleteComment, upload, removeAttachment].find((m) => m.isError)?.error

  return (
    <Modal open onClose={onClose} title={t?.title ?? 'Task'} wide>
      {!t ? (
        task.isError ? (
          <div className="p-6">
            <ErrorMessage>{errorMessage(task.error)}</ErrorMessage>
          </div>
        ) : (
          <FullPageSpinner />
        )
      ) : (
        <div className="grid gap-0 md:grid-cols-[1fr_260px]">
          <div className="space-y-5 p-5 sm:p-6">
            <div className="flex items-start gap-3">
              <input
                aria-label="Title"
                className="w-full rounded-lg border border-transparent bg-transparent px-1 py-1 text-xl font-semibold text-slate-900 hover:border-slate-300 focus:border-indigo-500 focus:outline-none disabled:hover:border-transparent dark:text-white dark:hover:border-slate-600"
                value={title}
                disabled={!canEdit}
                onChange={(e) => setTitle(e.target.value)}
                onBlur={() => title.trim() && title !== t.title && update.mutate({ title: title.trim() })}
              />
              <button onClick={onClose} aria-label="Close" className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700">
                ✕
              </button>
            </div>
            {error && <ErrorMessage>{errorMessage(error)}</ErrorMessage>}

            <Field label="Description">
              <Textarea
                value={description}
                disabled={!canEdit}
                placeholder="Add more detail…"
                onChange={(e) => setDescription(e.target.value)}
                onBlur={() => description !== t.description && update.mutate({ description })}
              />
            </Field>

            <section>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-semibold">Attachments</h3>
                {canEdit && (
                  <>
                    <Button variant="secondary" className="px-2.5 py-1 text-xs" loading={upload.isPending} onClick={() => fileInput.current?.click()}>
                      Upload file
                    </Button>
                    <input
                      ref={fileInput}
                      type="file"
                      hidden
                      onChange={(e) => {
                        const file = e.target.files?.[0]
                        if (file) upload.mutate(file)
                        e.target.value = ''
                      }}
                    />
                  </>
                )}
              </div>
              {attachments.data?.items.length ? (
                <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 dark:divide-slate-700 dark:border-slate-700">
                  {attachments.data.items.map((a) => (
                    <li key={a.id} className="flex items-center gap-3 px-3 py-2 text-sm">
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-500 uppercase dark:bg-slate-700 dark:text-slate-300">
                        {a.filename.split('.').pop()}
                      </span>
                      <button className="min-w-0 flex-1 truncate text-left hover:underline" onClick={() => endpoints.downloadAttachment(a)}>
                        {a.filename}
                      </button>
                      <span className="text-xs text-slate-500">{formatBytes(a.size)}</span>
                      {canEdit && (
                        <button className="text-xs text-slate-400 hover:text-red-600" onClick={() => removeAttachment.mutate(a.id)} aria-label={`Delete ${a.filename}`}>
                          Delete
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No files. Max 10 MB: images, PDF, text, CSV, zip, docx, xlsx.</p>
              )}
            </section>

            <section>
              <h3 className="mb-3 text-sm font-semibold">Comments</h3>
              <ul className="space-y-4">
                {comments.data?.items.map((c) => (
                  <li key={c.id} className="flex gap-3">
                    {c.author && <Avatar user={c.author} size="sm" />}
                    <div className="min-w-0 flex-1">
                      <p className="text-xs text-slate-500">
                        <span className="font-medium text-slate-800 dark:text-slate-200">{c.author?.full_name || c.author?.username}</span> · {timeAgo(c.created_at)}
                        {(c.author?.id === user?.id || isAdmin) && canEdit && (
                          <button className="ml-2 hover:text-red-600" onClick={() => deleteComment.mutate(c.id)}>
                            delete
                          </button>
                        )}
                      </p>
                      <CommentBody body={c.body} />
                    </div>
                  </li>
                ))}
              </ul>
              {canEdit && (
                <form
                  className="mt-4 space-y-2"
                  onSubmit={(e: FormEvent) => {
                    e.preventDefault()
                    if (comment.trim()) addComment.mutate()
                  }}
                >
                  <Textarea className="min-h-16" placeholder="Write a comment… use @username to notify someone" value={comment} onChange={(e) => setComment(e.target.value)} aria-label="New comment" />
                  <Button type="submit" loading={addComment.isPending} disabled={!comment.trim()}>
                    Comment
                  </Button>
                </form>
              )}
            </section>
          </div>

          <aside className="space-y-4 border-t border-slate-100 bg-slate-50/70 p-5 md:rounded-r-2xl md:border-t-0 md:border-l dark:border-slate-700 dark:bg-slate-900/40">
            <Field label="Status">
              <Select value={t.column_id} disabled={!canEdit} onChange={(e) => move.mutate(Number(e.target.value))}>
                {board.columns.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Priority">
              <Select value={t.priority} disabled={!canEdit} onChange={(e) => update.mutate({ priority: e.target.value as Priority })}>
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {p[0].toUpperCase() + p.slice(1)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Assignee">
              <Select
                value={t.assignee?.id ?? ''}
                disabled={!canEdit}
                onChange={(e) => update.mutate({ assignee_id: e.target.value ? Number(e.target.value) : null })}
              >
                <option value="">Unassigned</option>
                {members.map((m) => (
                  <option key={m.user.id} value={m.user.id}>
                    {m.user.full_name || m.user.username}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Due date">
              <Input type="date" value={t.due_date ?? ''} disabled={!canEdit} onChange={(e) => update.mutate({ due_date: e.target.value || null })} />
            </Field>
            <div>
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Labels</span>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {board.labels.map((l) => {
                  const on = t.labels.some((x) => x.id === l.id)
                  return (
                    <button
                      key={l.id}
                      disabled={!canEdit}
                      aria-pressed={on}
                      onClick={() => update.mutate({ label_ids: on ? t.labels.filter((x) => x.id !== l.id).map((x) => x.id) : [...t.labels.map((x) => x.id), l.id] })}
                      className={clsx('rounded-md px-2 py-0.5 text-xs font-semibold transition', on ? 'text-white' : 'bg-transparent opacity-60 ring-1 ring-current ring-inset hover:opacity-100')}
                      style={on ? { backgroundColor: l.color } : { color: l.color }}
                    >
                      {l.name}
                    </button>
                  )
                })}
                {board.labels.length === 0 && <span className="text-xs text-slate-500">No labels on this board.</span>}
              </div>
            </div>
            <div>
              <h3 className="mb-2 text-sm font-medium text-slate-700 dark:text-slate-300">History</h3>
              <ActivityFeed workspaceId={board.workspace_id} taskId={taskId} limit={8} />
            </div>
            {canEdit && (
              <Button variant="danger" className="w-full" loading={remove.isPending} onClick={() => confirm('Delete this task?') && remove.mutate()}>
                Delete task
              </Button>
            )}
          </aside>
        </div>
      )}
    </Modal>
  )
}
