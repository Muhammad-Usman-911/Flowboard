import { useRef, useState } from 'react'
import { Link } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import { Logo } from '../components/Layout'

/** Files in frontend/public/media, rendered with Capturizy (see docs/DEPLOYMENT.md for hosting). */
export const TOUR_VIDEO = '/media/flowboard-tour.mp4'
export const TOUR_POSTER = '/media/flowboard-tour.jpg'

/** Chapters of the walkthrough video: `at` is the start time in seconds. */
export const TOUR_CHAPTERS = [
  { at: 3, title: 'Log in', text: 'Sign in with your account, or try the demo owner account.' },
  { at: 7, title: 'Create a workspace', text: 'A workspace holds your team, its roles and its boards.' },
  { at: 19, title: 'Add boards', text: 'Give every project its own Kanban board.' },
  { at: 26, title: 'Invite your team', text: 'Invite teammates by email as Admin, Member or Viewer.' },
  { at: 39, title: 'Open a board', text: 'Search and filter tasks by assignee, priority, label or due date.' },
  { at: 51, title: 'Work on a task', text: 'Edit details, attach files, comment and @mention teammates.' },
  { at: 62, title: 'Drag cards', text: 'Move cards between columns. Everyone sees the change live.' },
  { at: 73, title: 'Track progress', text: 'Analytics show status, overdue work and completion per member.' },
] as const

const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

/** Public "how to use Flowboard" page with the walkthrough video and clickable chapters. */
export function TourPage() {
  const { user } = useAuth()
  const video = useRef<HTMLVideoElement>(null)
  const [time, setTime] = useState(0)
  const current = TOUR_CHAPTERS.reduce((found, c, i) => (time >= c.at ? i : found), -1)

  function seek(at: number) {
    const v = video.current
    if (!v) return
    v.currentTime = at
    void v.play().catch(() => {}) // autoplay can be blocked; the user can press play
    v.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-slate-50 to-sky-50 dark:from-slate-950 dark:via-slate-950 dark:to-indigo-950/40">
      <header className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4">
        <Link to="/" aria-label="Flowboard home">
          <Logo />
        </Link>
        <div className="ml-auto flex items-center gap-2">
          {user ? (
            <Link to="/workspaces" className="rounded-lg bg-indigo-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-indigo-500">
              Open my workspaces
            </Link>
          ) : (
            <>
              <Link to="/login" className="rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-white/70 dark:text-slate-300 dark:hover:bg-slate-800">
                Log in
              </Link>
              <Link to="/register" className="rounded-lg bg-indigo-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-indigo-500">
                Create account
              </Link>
            </>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 pt-6 pb-16">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold tracking-wide text-indigo-600 uppercase dark:text-indigo-400">Product tour</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl dark:text-white">How to use Flowboard</h1>
          <p className="mt-3 text-slate-600 dark:text-slate-400">
            From your first login to a live board your whole team works on, in 90 seconds.
          </p>
        </div>

        <div className="mt-8 overflow-hidden rounded-2xl border border-slate-200 bg-slate-900 shadow-2xl shadow-indigo-200/50 dark:border-slate-800 dark:shadow-none">
          <video
            ref={video}
            className="aspect-video w-full"
            src={TOUR_VIDEO}
            poster={TOUR_POSTER}
            controls
            playsInline
            preload="metadata"
            onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
          >
            Your browser cannot play this video. <a href={TOUR_VIDEO}>Download it</a> instead.
          </video>
        </div>

        <h2 className="mt-12 text-xl font-semibold text-slate-900 dark:text-white">Step by step</h2>
        <ol className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {TOUR_CHAPTERS.map((c, i) => (
            <li key={c.title}>
              <button
                onClick={() => seek(c.at)}
                aria-current={i === current ? 'step' : undefined}
                className={`h-full w-full rounded-xl border p-4 text-left transition hover:-translate-y-0.5 hover:shadow-md ${
                  i === current
                    ? 'border-indigo-400 bg-indigo-50 dark:border-indigo-500 dark:bg-indigo-950/50'
                    : 'border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900'
                }`}
              >
                <span className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-600 text-white">{i + 1}</span>
                  {clock(c.at)}
                </span>
                <span className="mt-3 block font-semibold text-slate-900 dark:text-white">{c.title}</span>
                <span className="mt-1 block text-sm text-slate-600 dark:text-slate-400">{c.text}</span>
              </button>
            </li>
          ))}
        </ol>

        <div className="mt-12 rounded-2xl border border-slate-200 bg-white p-6 text-center sm:p-8 dark:border-slate-800 dark:bg-slate-900">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Try it yourself</h2>
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
            Log in as <code>owner@flowboard.dev</code> with password <code>Password123</code> (demo data), then open the
            board in a second browser as <code>member@flowboard.dev</code> and drag a card to see live updates.
          </p>
          <Link
            to={user ? '/workspaces' : '/login'}
            className="mt-5 inline-block rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-indigo-500"
          >
            {user ? 'Go to my workspaces' : 'Log in and start'}
          </Link>
        </div>
      </main>
    </div>
  )
}
