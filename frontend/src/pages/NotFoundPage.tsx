import { Link } from 'react-router'

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 text-center">
      <p className="text-5xl font-bold text-indigo-600">404</p>
      <p className="text-slate-600 dark:text-slate-400">This page does not exist.</p>
      <Link to="/workspaces" className="text-sm font-medium text-indigo-600 hover:underline">
        Back to your workspaces
      </Link>
    </div>
  )
}
