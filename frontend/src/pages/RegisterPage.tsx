import { useState } from 'react'
import { useAuthStore } from '../store/authStore'

interface RegisterPageProps {
  onSwitchToLogin: () => void
}

export default function RegisterPage({ onSwitchToLogin }: RegisterPageProps) {
  const { register, isLoading } = useAuthStore()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (password !== confirmPassword) {
      setError('两次密码输入不一致')
      return
    }

    try {
      await register(username, password)
    } catch (err: any) {
      setError(err.message || '注册失败')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-paper-light">
      <div className="w-full max-w-sm mx-4">
        <div className="text-center mb-10">
          <h1 className="text-2xl font-song font-semibold text-ink tracking-wider mb-2">
            创建账号
          </h1>
          <p className="text-sm text-ink-lighter font-kai">注册后即可开始使用 Data Chat</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs text-ink-lighter mb-1 font-kai">用户名</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="ink-input text-sm w-full"
              placeholder="至少 2 个字符"
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
              placeholder="至少 6 位"
              required
              minLength={6}
            />
          </div>

          <div>
            <label className="block text-xs text-ink-lighter mb-1 font-kai">确认密码</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              className="ink-input text-sm w-full"
              placeholder="再次输入密码"
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
            {isLoading ? '注册中…' : '注册'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-ink-lighter font-kai">
          已有账号？{' '}
          <button
            onClick={onSwitchToLogin}
            className="text-celadon hover:underline"
          >
            去登录
          </button>
        </p>
      </div>
    </div>
  )
}
