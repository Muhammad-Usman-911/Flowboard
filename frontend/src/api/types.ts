// TypeScript mirrors of the backend's Pydantic schemas (backend/app/schemas/*).
// If you change a schema in Python, change it here too.

export type Role = 'owner' | 'admin' | 'member' | 'viewer'
export type Priority = 'low' | 'medium' | 'high' | 'urgent'

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface ApiErrorBody {
  detail: string
  code: string
  errors?: { field: string; message: string }[]
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  expires_in: number
}

export interface UserPublic {
  id: number
  username: string
  full_name: string
}

export interface UserMe extends UserPublic {
  email: string
  created_at: string
}

export interface Workspace {
  id: number
  name: string
  description: string
  owner_id: number
  created_at: string
  my_role: Role
}

export interface Member {
  user: UserPublic
  role: Role
  created_at: string
}

export interface Column {
  id: number
  board_id: number
  title: string
  position: number
  is_done: boolean
}

export interface Label {
  id: number
  board_id: number
  name: string
  color: string
}

export interface Board {
  id: number
  workspace_id: number
  name: string
  description: string
  created_at: string
}

export interface BoardDetail extends Board {
  columns: Column[]
  labels: Label[]
}

export interface Task {
  id: number
  board_id: number
  column_id: number
  title: string
  description: string
  priority: Priority
  due_date: string | null
  position: number
  assignee: UserPublic | null
  created_by_id: number | null
  labels: Label[]
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface TaskFilters {
  assignee_id?: number
  priority?: Priority
  label_id?: number
  overdue?: boolean
  q?: string
}

export interface Comment {
  id: number
  task_id: number
  author: UserPublic | null
  body: string
  created_at: string
}

export interface Attachment {
  id: number
  task_id: number
  uploader_id: number | null
  filename: string
  content_type: string
  size: number
  created_at: string
}

export interface Notification {
  id: number
  type: 'mention' | 'assigned'
  message: string
  task_id: number | null
  board_id: number | null
  is_read: boolean
  created_at: string
}

export interface Activity {
  id: number
  workspace_id: number
  board_id: number | null
  task_id: number | null
  user: UserPublic | null
  action: string
  summary: string
  details: Record<string, unknown>
  created_at: string
}

export interface Analytics {
  total_tasks: number
  completed_tasks: number
  overdue_tasks: number
  tasks_per_status: { title: string; is_done: boolean; count: number }[]
  completion_by_member: {
    user: UserPublic
    assigned: number
    completed: number
    completion_rate: number
  }[]
  tasks_created_per_week: { week_start: string; count: number }[]
}

/** A message received on /ws/boards/{id}. */
export interface BoardEvent {
  type: string
  board_id: number
  actor_id: number | null
  data: Record<string, unknown>
}
