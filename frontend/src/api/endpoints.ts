// One small typed function per backend endpoint. Components never build URLs themselves.

import { api } from './client'
import type {
  Activity,
  Analytics,
  Attachment,
  Board,
  BoardDetail,
  Column,
  Comment,
  Label,
  Member,
  Notification,
  Page,
  Priority,
  Role,
  Task,
  TaskFilters,
  TokenPair,
  UserMe,
  Workspace,
} from './types'

const data = <T>(p: Promise<{ data: T }>) => p.then((r) => r.data)

// --- auth & profile ---
export const login = (email: string, password: string) =>
  data(api.post<TokenPair>('/auth/login', { email, password }))
export const register = (body: { email: string; username: string; full_name: string; password: string }) =>
  data(api.post<UserMe>('/auth/register', body))
export const getMe = () => data(api.get<UserMe>('/users/me'))
export const updateMe = (body: { full_name?: string; password?: string }) =>
  data(api.patch<UserMe>('/users/me', body))

// --- notifications ---
export const listNotifications = (unreadOnly = false) =>
  data(api.get<Page<Notification>>('/notifications', { params: { unread_only: unreadOnly, limit: 30 } }))
export const markNotificationRead = (id: number) => data(api.post<Notification>(`/notifications/${id}/read`))
export const markAllNotificationsRead = () => data(api.post('/notifications/read-all'))

// --- workspaces & members ---
export const listWorkspaces = () => data(api.get<Page<Workspace>>('/workspaces', { params: { limit: 100 } }))
export const getWorkspace = (id: number) => data(api.get<Workspace>(`/workspaces/${id}`))
export const createWorkspace = (body: { name: string; description?: string }) =>
  data(api.post<Workspace>('/workspaces', body))
export const listMembers = (workspaceId: number) =>
  data(api.get<Page<Member>>(`/workspaces/${workspaceId}/members`, { params: { limit: 200 } }))
export const inviteMember = (workspaceId: number, email: string, role: Role) =>
  data(api.post<Member>(`/workspaces/${workspaceId}/members`, { email, role }))
export const changeMemberRole = (workspaceId: number, userId: number, role: Role) =>
  data(api.patch<Member>(`/workspaces/${workspaceId}/members/${userId}`, { role }))
export const removeMember = (workspaceId: number, userId: number) =>
  api.delete(`/workspaces/${workspaceId}/members/${userId}`)
export const listActivity = (workspaceId: number, params: { board_id?: number; task_id?: number; limit?: number }) =>
  data(api.get<Page<Activity>>(`/workspaces/${workspaceId}/activity`, { params }))
export const getAnalytics = (workspaceId: number, boardId?: number) =>
  data(api.get<Analytics>(`/workspaces/${workspaceId}/analytics`, { params: { board_id: boardId } }))

// --- boards, columns, labels ---
export const listBoards = (workspaceId: number) =>
  data(api.get<Page<Board>>(`/workspaces/${workspaceId}/boards`, { params: { limit: 100 } }))
export const createBoard = (workspaceId: number, body: { name: string; description?: string }) =>
  data(api.post<Board>(`/workspaces/${workspaceId}/boards`, body))
export const getBoard = (boardId: number) => data(api.get<BoardDetail>(`/boards/${boardId}`))
export const createColumn = (boardId: number, title: string) =>
  data(api.post<Column>(`/boards/${boardId}/columns`, { title }))
export const createLabel = (boardId: number, name: string, color: string) =>
  data(api.post<Label>(`/boards/${boardId}/labels`, { name, color }))

// --- tasks ---
/** Max page size; a Kanban board shows every task at once. */
export const TASK_PAGE_LIMIT = 200

export const listTasks = (boardId: number, filters: TaskFilters = {}) =>
  data(api.get<Page<Task>>(`/boards/${boardId}/tasks`, { params: { ...filters, limit: TASK_PAGE_LIMIT } }))
export const getTask = (taskId: number) => data(api.get<Task>(`/tasks/${taskId}`))
export interface TaskInput {
  title?: string
  description?: string
  column_id?: number
  priority?: Priority
  due_date?: string | null
  assignee_id?: number | null
  label_ids?: number[]
}
export const createTask = (boardId: number, body: TaskInput & { title: string }) =>
  data(api.post<Task>(`/boards/${boardId}/tasks`, body))
export const updateTask = (taskId: number, body: TaskInput) => data(api.patch<Task>(`/tasks/${taskId}`, body))
export const moveTask = (taskId: number, columnId: number, position: number) =>
  data(api.post<Task>(`/tasks/${taskId}/move`, { column_id: columnId, position }))
export const deleteTask = (taskId: number) => api.delete(`/tasks/${taskId}`)

// --- comments & attachments ---
export const listComments = (taskId: number) =>
  data(api.get<Page<Comment>>(`/tasks/${taskId}/comments`, { params: { limit: 200 } }))
export const addComment = (taskId: number, body: string) =>
  data(api.post<Comment>(`/tasks/${taskId}/comments`, { body }))
export const deleteComment = (commentId: number) => api.delete(`/comments/${commentId}`)
export const listAttachments = (taskId: number) =>
  data(api.get<Page<Attachment>>(`/tasks/${taskId}/attachments`, { params: { limit: 200 } }))
export const uploadAttachment = (taskId: number, file: File) => {
  const form = new FormData()
  form.append('file', file)
  return data(api.post<Attachment>(`/tasks/${taskId}/attachments`, form))
}
export const deleteAttachment = (id: number) => api.delete(`/attachments/${id}`)
/** Downloads go through axios (not a plain link) so the Authorization header is sent. */
export async function downloadAttachment(attachment: Attachment) {
  const res = await api.get<Blob>(`/attachments/${attachment.id}/download`, { responseType: 'blob' })
  const url = URL.createObjectURL(res.data)
  const link = document.createElement('a')
  link.href = url
  link.download = attachment.filename
  link.click()
  URL.revokeObjectURL(url)
}
