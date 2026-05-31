import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { useTranslation } from 'react-i18next'

export default function RegisterPage() {
  const { t } = useTranslation()
  const register = useAuthStore(s => s.register)
  const isLoading = useAuthStore(s => s.isLoading)
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (password !== confirmPassword) {
      setError(t('auth.passwordMismatch'))
      return
    }

    try {
      await register(username, password)
      navigate('/', { replace: true })
    } catch (err: any) {
      setError(err.message || t('auth.registerFailed'))
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-paper-light">
      <div className="w-full max-w-sm mx-4">
        <div className="text-center mb-10">
          <h1 className="text-2xl font-song font-semibold text-ink tracking-wider mb-2">
            {t('app.name')}
          </h1>
          <p className="text-sm text-ink-lighter font-kai">{t('auth.registerSubtitle')}</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs text-ink-lighter mb-1 font-kai">{t('auth.username')}</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="ink-input text-sm w-full"
              placeholder={t('auth.usernamePlaceholder')}
              required
              minLength={2}
            />
          </div>

          <div>
            <label className="block text-xs text-ink-lighter mb-1 font-kai">{t('auth.password')}</label>
            <input
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="ink-input text-sm w-full"
              placeholder={t('auth.passwordPlaceholder')}
              required
              minLength={6}
            />
          </div>

          <div>
            <label className="block text-xs text-ink-lighter mb-1 font-kai">{t('auth.confirmPassword')}</label>
            <input
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              className="ink-input text-sm w-full"
              placeholder={t('auth.confirmPasswordPlaceholder')}
              required
              minLength={6}
            />
          </div>

          {error && (
            <div className="text-cinnabar text-xs text-center">{error}</div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="btn-celadon w-full"
          >
            {isLoading ? t('auth.registering') : t('auth.register')}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-ink-lighter font-kai">
          {t('auth.hasAccount')}{' '}
          <Link to="/login" className="text-celadon hover:underline">
            {t('auth.goToLogin')}
          </Link>
        </p>
      </div>
    </div>
  )
}
