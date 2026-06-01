import { useState, useEffect, useRef } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { useTranslation } from 'react-i18next'
import AuthLayout from '../components/AuthLayout'

const STORAGE_KEY_USERNAME = 'remembered_username'
const STORAGE_KEY_PASSWORD = 'remembered_password'
const STORAGE_KEY_REMEMBER = 'remember_me'

export default function LoginPage() {
  const { t } = useTranslation()
  const login = useAuthStore(s => s.login)
  const user = useAuthStore(s => s.user)
  const isLoading = useAuthStore(s => s.isLoading)
  const navigate = useNavigate()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [rememberMe, setRememberMe] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isAutoLogging, setIsAutoLogging] = useState(false)
  const autoLoginAttempted = useRef(false)

  useEffect(() => {
    if (user) {
      navigate('/', { replace: true })
      return
    }

    if (autoLoginAttempted.current) return
    autoLoginAttempted.current = true

    const savedRemember = localStorage.getItem(STORAGE_KEY_REMEMBER)
    const savedUsername = localStorage.getItem(STORAGE_KEY_USERNAME)
    const savedPassword = localStorage.getItem(STORAGE_KEY_PASSWORD)

    if (savedRemember === 'true' && savedUsername && savedPassword) {
      setRememberMe(true)
      setUsername(savedUsername)
      setPassword(savedPassword)
      performAutoLogin(savedUsername, savedPassword)
    }
  }, [])

  const performAutoLogin = async (uname: string, pwd: string) => {
    setIsAutoLogging(true)
    try {
      await login(uname, pwd)
      navigate('/', { replace: true })
    } catch {
      setIsAutoLogging(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await login(username, password)
      if (rememberMe) {
        localStorage.setItem(STORAGE_KEY_USERNAME, username)
        localStorage.setItem(STORAGE_KEY_PASSWORD, password)
        localStorage.setItem(STORAGE_KEY_REMEMBER, 'true')
      } else {
        localStorage.removeItem(STORAGE_KEY_USERNAME)
        localStorage.removeItem(STORAGE_KEY_PASSWORD)
        localStorage.removeItem(STORAGE_KEY_REMEMBER)
      }
      navigate('/', { replace: true })
    } catch (err: any) {
      setError(err.message || t('auth.loginFailed'))
    }
  }

  if (isAutoLogging) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-paper-light">
        <div className="text-center">
          <p className="text-sm text-ink-lighter font-kai">{t('app.autoLogin')}</p>
        </div>
      </div>
    )
  }

  return (
    <AuthLayout
      subtitle={t('auth.subtitle')}
      footer={<>{t('auth.noAccount')} <Link to="/register" className="text-celadon hover:underline">{t('auth.goToRegister')}</Link></>}
    >
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
            autoComplete="current-password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            className="ink-input text-sm w-full"
            placeholder={t('auth.passwordPlaceholder')}
            required
            minLength={6}
          />
        </div>

        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={e => setRememberMe(e.target.checked)}
              className="w-4 h-4 rounded border-ink-lighter text-celadon focus:ring-celadon"
            />
            <span className="text-xs text-ink-lighter font-kai">{t('auth.rememberMe')}</span>
          </label>
        </div>

        {error && (
          <div className="text-cinnabar text-xs text-center">{error}</div>
        )}

        <button
          type="submit"
          disabled={isLoading}
          className="btn-celadon w-full"
        >
          {isLoading ? t('auth.loggingIn') : t('auth.login')}
        </button>
      </form>
    </AuthLayout>
  )
}
