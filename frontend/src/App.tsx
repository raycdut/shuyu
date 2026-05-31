import { Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
import AppLayout from './components/AppLayout'
import IndexPage from './pages/IndexPage'
import ChatPage from './pages/ChatPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import AdminSettingsPage from './pages/AdminSettingsPage'
import { useAuthStore } from './store/authStore'
import { useTranslation } from 'react-i18next'

export default function App() {
  const { t } = useTranslation()
  const user = useAuthStore(s => s.user)
  const isInitialized = useAuthStore(s => s.isInitialized)

  useEffect(() => {
    useAuthStore.getState().checkAuth()
  }, [])

  if (!isInitialized) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-paper-light">
        <p className="text-ink-lighter font-kai">{t('app.loading')}</p>
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
        <Route path="/" element={<IndexPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/admin" element={<AdminSettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
