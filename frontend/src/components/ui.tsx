// Small, reusable UI pieces styled with Tailwind. Keeping them here means pages read
// like a description of the screen instead of a wall of class names.

import clsx from 'clsx'
import { useEffect, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import type { Priority, Role, UserPublic } from '../api/types'
import { initials } from '../lib/format'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

export function Button({
  variant = 'primary',
  className,
  loading,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  return (
    <button
      className={clsx(
        'inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 disabled:cursor-not-allowed disabled:opacity-50',
        variant === 'primary' && 'bg-indigo-600 text-white shadow-sm hover:bg-indigo-500',
        variant === 'secondary' &&
          'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700',
        variant === 'ghost' && 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800',
        variant === 'danger' && 'bg-red-600 text-white hover:bg-red-500',
        className,
      )}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading && <Spinner small />}
      {children}
    </button>
  )
}

// Fields are full width unless the caller passes its own (unprefixed) width class.
const width = (className?: string) => !/(^|\s)w-/.test(className ?? '') && 'w-full'

const fieldClass =
  'rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/30 focus:outline-none disabled:opacity-60 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100'

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={clsx(fieldClass, width(className), className)} {...props} />
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={clsx(fieldClass, width(className), 'min-h-24', className)} {...props} />
}

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={clsx(fieldClass, width(className), 'pr-8', className)} {...props} />
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-sm font-medium text-slate-700 dark:text-slate-300">{label}</span>
      {children}
      {hint && <span className="block text-xs text-slate-500 dark:text-slate-400">{hint}</span>}
    </label>
  )
}

export function Spinner({ small }: { small?: boolean }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={clsx(
        'inline-block animate-spin rounded-full border-2 border-current border-t-transparent opacity-70',
        small ? 'h-4 w-4' : 'h-6 w-6 text-indigo-500',
      )}
    />
  )
}

export function FullPageSpinner() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <Spinner />
    </div>
  )
}

export function ErrorMessage({ children, onRetry }: { children: ReactNode; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300">
      <span>{children}</span>
      {onRetry && (
        <button className="font-medium underline" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={clsx('rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700/70 dark:bg-slate-800/60', className)}>
      {children}
    </div>
  )
}

const AVATAR_COLORS = ['bg-indigo-500', 'bg-sky-500', 'bg-emerald-500', 'bg-amber-500', 'bg-rose-500', 'bg-violet-500', 'bg-teal-500']

export function Avatar({ user, size = 'md' }: { user: UserPublic; size?: 'sm' | 'md' }) {
  return (
    <span
      title={`${user.full_name || user.username} (@${user.username})`}
      className={clsx(
        'inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white ring-2 ring-white dark:ring-slate-800',
        AVATAR_COLORS[user.id % AVATAR_COLORS.length],
        size === 'sm' ? 'h-6 w-6 text-[10px]' : 'h-8 w-8 text-xs',
      )}
    >
      {initials(user.full_name || user.username)}
    </span>
  )
}

const PRIORITY_STYLES: Record<Priority, string> = {
  low: 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300',
  medium: 'bg-sky-100 text-sky-700 dark:bg-sky-900/60 dark:text-sky-300',
  high: 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300',
  urgent: 'bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300',
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  return <span className={clsx('rounded-md px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide', PRIORITY_STYLES[priority])}>{priority}</span>
}

export function RoleBadge({ role }: { role: Role }) {
  return (
    <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700 capitalize dark:bg-indigo-950 dark:text-indigo-300">
      {role}
    </span>
  )
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/50 p-4 backdrop-blur-sm sm:p-8" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={clsx('w-full rounded-2xl bg-white shadow-2xl dark:bg-slate-800', wide ? 'max-w-4xl' : 'max-w-md')}
        onMouseDown={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center dark:border-slate-700">
      <p className="font-medium text-slate-700 dark:text-slate-200">{title}</p>
      {children && <div className="mt-2 text-sm text-slate-500 dark:text-slate-400">{children}</div>}
    </div>
  )
}
