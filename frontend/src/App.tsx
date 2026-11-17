import { Navigate, Route, Routes } from 'react-router'
import { AuthProvider } from './auth/AuthContext'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { Layout } from './components/Layout'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { BoardPage } from './pages/BoardPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { ProfilePage } from './pages/ProfilePage'
import { RegisterPage } from './pages/RegisterPage'
import { WorkspacePage } from './pages/WorkspacePage'
import { WorkspacesPage } from './pages/WorkspacesPage'

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<Navigate to="/workspaces" replace />} />
            <Route path="/workspaces" element={<WorkspacesPage />} />
            <Route path="/workspaces/:workspaceId" element={<WorkspacePage />} />
            <Route path="/workspaces/:workspaceId/analytics" element={<AnalyticsPage />} />
            <Route path="/boards/:boardId" element={<BoardPage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Route>
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AuthProvider>
  )
}
