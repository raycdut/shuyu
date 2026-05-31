import { useState } from 'react'
import { useAuthStore } from '../store/authStore'

interface LoginPageProps {
  onSwitchToRegister: () => void
}

export default function LoginPage({ onSwitchToRegister }: LoginPageProps) {
  const { login, isLoading } = useAuthStore()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await login(username, password)
    } catch (err: any) {
      setError(err.message || '登录失败')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-paper-light">
      <div className="w-full max-w-sm mx-4">
        <div className="text-center mb-10">
          <h1 className="text-2xl font-song font-semibold text-ink tracking-wider mb-2">
            Data Chat
          </h1>
          <p className="text-sm text-ink-lighter font-kai">问你的数据</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs text-ink-lighter mb-1 font-kai">用户名</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="ink-input text-sm w-full"
              placeholder="请输入用户名"
              required
              minLength={2}
            />
          </div>

          <div>
            <label className="block text-xs text-ink-lighter mb-1 font-kai">密码</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="ink-input text-sm w-full"
              placeholder="请输入密码"
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
            {isLoading ? '登录中…' : '登录'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-ink-lighter font-kai">
          没有账号？{' '}
          <button
            onClick={onSwitchToRegister}
            className="text-celadon hover:underline"
          >
            去注册
          </button>
        </p>
      </div>
    </div>
  )
}
