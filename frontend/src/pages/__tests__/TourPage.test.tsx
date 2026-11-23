import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../../auth/AuthContext'
import { TOUR_CHAPTERS, TOUR_VIDEO, TourPage } from '../TourPage'

function renderTour() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/tour']}>
        <AuthProvider>
          <TourPage />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('TourPage', () => {
  it('shows the walkthrough video and every chapter', () => {
    const { container } = renderTour()
    expect(screen.getByRole('heading', { name: 'How to use Flowboard' })).toBeInTheDocument()
    expect(container.querySelector('video')).toHaveAttribute('src', TOUR_VIDEO)
    for (const c of TOUR_CHAPTERS) expect(screen.getByRole('button', { name: new RegExp(c.title) })).toBeInTheDocument()
  })

  it('jumps the video to a chapter when it is clicked', async () => {
    const { container } = renderTour()
    const video = container.querySelector('video')!
    video.play = vi.fn().mockResolvedValue(undefined)
    video.scrollIntoView = vi.fn()
    await userEvent.click(screen.getByText('Drag cards'))
    expect(video.currentTime).toBe(62)
    expect(video.play).toHaveBeenCalled()
  })
})
