// Where the JWTs live in the browser.
//
// localStorage is simple and survives reloads, but any script on the page can read it,
// so an XSS bug would leak tokens. A common upgrade is to keep the refresh token in an
// httpOnly cookie instead (see the exercises in docs/LEARNING_GUIDE.md).

const ACCESS = 'flowboard-access'
const REFRESH = 'flowboard-refresh'

export const tokenStore = {
  get access(): string | null {
    return localStorage.getItem(ACCESS)
  },
  get refresh(): string | null {
    return localStorage.getItem(REFRESH)
  },
  set(access: string, refresh: string) {
    localStorage.setItem(ACCESS, access)
    localStorage.setItem(REFRESH, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS)
    localStorage.removeItem(REFRESH)
  },
}
