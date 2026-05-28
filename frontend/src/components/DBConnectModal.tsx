import { useState } from 'react'
import type { DBConnectRequest } from '../types'
import { api } from '../api'

interface DBConnectModalProps {
  open: boolean
  onClose: () => void
  onConnected: () => void
}

const DB_TYPES = [
  { value: 'duckdb', label: 'DuckDB' },
  { value: 'sqlite', label: 'SQLite' },
  { value: 'postgres', label: 'PostgreSQL' },
  { value: 'mysql', label: 'MySQL' },
  { value: 'clickhouse', label: 'ClickHouse' },
  { value: 'snowflake', label: 'Snowflake' },
]

export default function DBConnectModal({ open, onClose, onConnected }: DBConnectModalProps) {
  const [form, setForm] = useState<DBConnectRequest>({
    name: '',
    type: 'duckdb',
    path: '',
    host: '',
    port: 5432,
    user: '',
    password: '',
    database: '',
    connection_string: '',
    include_tables: [],
    exclude_tables: [],
  })
  const [includeText, setIncludeText] = useState('')
  const [excludeText, setExcludeText] = useState('')
  const [testing, setTesting] = useState(false)
  const [connecting, setConnecting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null)
  const [error, setError] = useState('')

  if (!open) return null

  const isLocal = form.type === 'duckdb' || form.type === 'sqlite'
  const isRemote = !isLocal

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    setError('')
    try {
      const res = await api.testConnection(form)
      setTestResult(res)
    } catch (err: any) {
      setTestResult({ ok: false, message: err.message })
    } finally {
      setTesting(false)
    }
  }

  const handleConnect = async () => {
    if (!form.name.trim()) { setError('请输入数据库名称'); return }
    setConnecting(true)
    setError('')
    try {
      await api.connectDatabase({
        ...form,
        include_tables: includeText.split(',').map(s => s.trim()).filter(Boolean),
        exclude_tables: excludeText.split(',').map(s => s.trim()).filter(Boolean),
      })
      onConnected()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setConnecting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20" onClick={onClose}>
      <div
        className="bg-paper-light paper-shadow-md rounded-sm w-full max-w-lg max-h-[80vh] overflow-y-auto mx-4"
        onClick={e => e.stopPropagation()}
      >
        {/* 标题 */}
        <div className="flex items-center justify-between px-6 py-4 ink-border border-t-0 border-x-0">
          <h2 className="text-base font-song font-semibold text-ink">添加数据库</h2>
          <button onClick={onClose} className="p-1 text-ink-lighter hover:text-ink hover:bg-smoke rounded-sm transition-colors">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="p-6 space-y-4">
          {/* 数据库类型 */}
          <div>
            <label className="block text-xs text-ink-lighter mb-1 font-kai">数据库类型</label>
            <select
              value={form.type}
              onChange={e => setForm({ ...form, type: e.target.value })}
              className="ink-input"
            >
              {DB_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>

          {/* 名称 */}
          <div>
            <label className="block text-xs text-ink-lighter mb-1 font-kai">名称</label>
            <input
              className="ink-input"
              placeholder="例：零售数据库"
              value={form.name}
              onChange={e => setForm({ ...form, name: e.target.value })}
            />
          </div>

          {/* 路径 (本地) */}
          {isLocal && (
            <div>
              <label className="block text-xs text-ink-lighter mb-1 font-kai">文件路径</label>
              <input
                className="ink-input"
                placeholder="./data/analytics.db"
                value={form.path}
                onChange={e => setForm({ ...form, path: e.target.value })}
              />
            </div>
          )}

          {/* 连接信息 (远程) */}
          {isRemote && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-ink-lighter mb-1 font-kai">主机</label>
                  <input className="ink-input" value={form.host} onChange={e => setForm({ ...form, host: e.target.value })} />
                </div>
                <div>
                  <label className="block text-xs text-ink-lighter mb-1 font-kai">端口</label>
                  <input type="number" className="ink-input" value={form.port} onChange={e => setForm({ ...form, port: Number(e.target.value) })} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-ink-lighter mb-1 font-kai">用户名</label>
                  <input className="ink-input" value={form.user} onChange={e => setForm({ ...form, user: e.target.value })} />
                </div>
                <div>
                  <label className="block text-xs text-ink-lighter mb-1 font-kai">密码</label>
                  <input type="password" className="ink-input" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
                </div>
              </div>
              <div>
                <label className="block text-xs text-ink-lighter mb-1 font-kai">数据库名</label>
                <input className="ink-input" value={form.database} onChange={e => setForm({ ...form, database: e.target.value })} />
              </div>
            </>
          )}

          {/* 连接字符串替代 */}
          <div>
            <label className="block text-xs text-ink-lighter mb-1 font-kai">连接字符串（可选，优先级高于上面字段）</label>
            <input
              className="ink-input"
              value={form.connection_string}
              onChange={e => setForm({ ...form, connection_string: e.target.value })}
            />
          </div>

          {/* 表过滤 */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-ink-lighter mb-1 font-kai">包含表（可选）</label>
              <input
                className="ink-input"
                placeholder="fct_*, dim_*"
                value={includeText}
                onChange={e => setIncludeText(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs text-ink-lighter mb-1 font-kai">排除表（可选）</label>
              <input
                className="ink-input"
                placeholder="temp_*"
                value={excludeText}
                onChange={e => setExcludeText(e.target.value)}
              />
            </div>
          </div>

          {/* 测试结果 */}
          {testResult && (
            <div className={`p-3 text-sm rounded-sm ${testResult.ok ? 'bg-celadon/10 text-celadon-dark' : 'bg-cinnabar/5 text-cinnabar'}`}>
              {testResult.ok ? '✅ ' : '❌ '}{testResult.message}
            </div>
          )}

          {/* 错误 */}
          {error && (
            <div className="p-3 text-sm rounded-sm bg-cinnabar/5 text-cinnabar">
              {error}
            </div>
          )}

          {/* 按钮组 */}
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={onClose} className="px-3 py-1.5 text-sm text-ink-light hover:bg-smoke rounded-sm transition-colors">
              取消
            </button>
            <button
              onClick={handleTest}
              disabled={testing}
              className="px-3 py-1.5 text-sm text-ink-light hover:bg-smoke ink-border rounded-sm transition-colors disabled:opacity-40"
            >
              {testing ? '测试中…' : '测试连接'}
            </button>
            <button
              onClick={handleConnect}
              disabled={connecting}
              className="btn-celadon"
            >
              {connecting ? '连接中…' : '保存并连接'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
