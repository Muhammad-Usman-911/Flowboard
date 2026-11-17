import { useCallback, useState } from 'react'

type Theme = 'light' | 'dark'

function current(): Theme {
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light'
}

/** Light/dark toggle. Tailwind's `dark:` styles apply when <html> has the `dark` class. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(current)
  const toggle = useCallback(() => {
    const next: Theme = current() === 'dark' ? 'light' : 'dark'
    document.documentElement.classList.toggle('dark', next === 'dark')
    try {
      localStorage.setItem('flowboard-theme', next)
    } catch {
      /* private mode: the choice just won't be remembered */
    }
    setTheme(next)
  }, [])
  return { theme, toggle }
}
