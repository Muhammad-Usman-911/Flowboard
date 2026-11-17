/** Same rules as the backend (backend/app/schemas/user.py), checked early for a nicer UX.
 *  The server still validates: never trust the browser alone. */
export function passwordProblem(password: string): string | null {
  if (password.length < 8) return 'Password must be at least 8 characters.'
  if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) return 'Password needs at least one letter and one digit.'
  return null
}
