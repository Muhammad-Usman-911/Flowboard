import type { Priority, Role } from '../api/types'

export function formatDate(iso: string | null): string {
  if (!iso) return ''
  const date = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso)
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function timeAgo(iso: string, now: Date = new Date()): string {
  const seconds = Math.round((now.getTime() - new Date(iso).getTime()) / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days}d ago`
  return formatDate(iso)
}

/** "2024-05-01" style date for today in the user's local time zone. */
export function todayISO(now: Date = new Date()): string {
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}

export function isOverdue(due: string | null, done: boolean, now: Date = new Date()): boolean {
  return !!due && !done && due < todayISO(now)
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  return (parts.length > 1 ? parts[0][0] + parts[1][0] : name.slice(0, 2)).toUpperCase()
}

const ROLE_RANK: Record<Role, number> = { viewer: 0, member: 1, admin: 2, owner: 3 }
/** Same rule as the backend's Role.at_least (backend/app/models/enums.py). */
export const atLeast = (role: Role | undefined, min: Role) => !!role && ROLE_RANK[role] >= ROLE_RANK[min]

export const PRIORITIES: Priority[] = ['low', 'medium', 'high', 'urgent']
