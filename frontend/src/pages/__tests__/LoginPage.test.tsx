import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { AuthProvider } from '../../auth/AuthContext'
import { passwordProblem } from '../../lib/validation'
import { LoginPage } from '../LoginPage'

function renderLogin() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/login']}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('LoginPage', () => {
  it('renders the form with a link to register', () => {
    renderLogin()
    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Create one' })).toHaveAttribute('href', '/register')
  })

  it('validates empty fields before calling the API', async () => {
    renderLogin()
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Enter your email and password.')
  })
})

describe('passwordProblem', () => {
  it('mirrors the backend password rules', () => {
    expect(passwordProblem('short1')).toMatch(/8 characters/)
    expect(passwordProblem('lettersonly')).toMatch(/letter and one digit/)
    expect(passwordProblem('Password123')).toBeNull()
  })
})
