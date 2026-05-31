import { Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import ChatPage from './pages/ChatPage'
import Dashboard from './components/Dashboard'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import AdminSettingsPage from './pages/AdminSettingsPage'
import DatabaseManagerPage from './pages/DatabaseManagerPage'
import { useAuthStore } from './store/authStore'

export default function App() {
  const user = useAuthStore(s => s.user)
  const isInitialized = useAuthStore(s => s.isInitialized)

  if (!isInitialized) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-paper-light">
        <p className="text-ink-lighter font-kai">加载中…</p>
      </div>
    )
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<ChatPage />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/admin" element={<AdminSettingsPage />} />
        <Route path="/databases" element={<DatabaseManagerPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
