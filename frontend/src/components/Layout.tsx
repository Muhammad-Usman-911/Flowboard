import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router'
import * as endpoints from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { useTheme } from '../hooks/useTheme'
import { timeAgo } from '../lib/format'
import { Avatar } from './ui'

export function Logo() {
  return (
    <span className="flex items-center gap-2 text-lg font-bold tracking-tight text-slate-900 dark:text-white">
      <img src="/favicon.svg" alt="" className="h-7 w-7" />
      Flowboard
    </span>
  )
}

function ThemeToggle() {
  const { theme, toggle } = useTheme()
  return (
    <button
      onClick={toggle}
      aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
    >
      {theme === 'dark' ? (
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
        </svg>
      )}
    </button>
  )
}

function NotificationBell() {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  // Polling every 30 s keeps the badge fresh. (Exercise: push these over a WebSocket.)
  const { data } = useQuery({ queryKey: ['notifications'], queryFn: () => endpoints.listNotifications(), refetchInterval: 30_000 })
  const unread = data?.items.filter((n) => !n.is_read).length ?? 0
  const markAll = useMutation({
    mutationFn: endpoints.markAllNotificationsRead,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  })

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={`Notifications (${unread} unread)`}
        className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
      >
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.9 1.9 0 0 0 3.4 0" />
        </svg>
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
            {unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-80 max-w-[calc(100vw-2rem)] rounded-xl border border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-800">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5 dark:border-slate-700">
            <span className="text-sm font-semibold">Notifications</span>
            <button className="text-xs text-indigo-600 hover:underline dark:text-indigo-400" onClick={() => markAll.mutate()}>
              Mark all read
            </button>
          </div>
          <ul className="max-h-96 overflow-y-auto">
            {data?.items.length === 0 && <li className="px-4 py-6 text-center text-sm text-slate-500">You're all caught up.</li>}
            {data?.items.map((n) => (
              <li key={n.id}>
                <button
                  className={clsx('block w-full px-4 py-2.5 text-left text-sm hover:bg-slate-50 dark:hover:bg-slate-700/50', !n.is_read && 'bg-indigo-50/60 dark:bg-indigo-950/30')}
                  onClick={async () => {
                    setOpen(false)
                    if (!n.is_read) await endpoints.markNotificationRead(n.id)
                    queryClient.invalidateQueries({ queryKey: ['notifications'] })
                    if (n.board_id) navigate(`/boards/${n.board_id}${n.task_id ? `?task=${n.task_id}` : ''}`)
                  }}
                >
                  <span className="block text-slate-800 dark:text-slate-100">{n.message}</span>
                  <span className="text-xs text-slate-500">{timeAgo(n.created_at)}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export function Layout() {
  const { user, logout } = useAuth()
  const navClass = ({ isActive }: { isActive: boolean }) =>
    clsx(
      'rounded-lg px-3 py-1.5 text-sm font-medium',
      isActive ? 'bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-white' : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white',
    )
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/85 backdrop-blur dark:border-slate-800 dark:bg-slate-950/85">
        <div className="mx-auto flex h-14 max-w-[1600px] items-center gap-2 px-4 sm:gap-4">
          <Link to="/workspaces">
            <Logo />
          </Link>
          <nav className="ml-2 hidden items-center gap-1 sm:flex">
            <NavLink to="/workspaces" className={navClass}>
              Workspaces
            </NavLink>
            <NavLink to="/profile" className={navClass}>
              Profile
            </NavLink>
            <NavLink to="/tour" className={navClass}>
              Tour
            </NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-1">
            <NotificationBell />
            <ThemeToggle />
            {user && (
              <Link to="/profile" className="ml-1">
                <Avatar user={user} />
              </Link>
            )}
            <button onClick={logout} className="ml-1 rounded-lg px-2.5 py-1.5 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800">
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1600px] px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
