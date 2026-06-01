import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import type { DBConnectRequest, DatabaseInfo } from '../types'
import { api } from '../api'
import { Modal } from './Modal'

interface DBConnectModalProps {
  open: boolean
  onClose: () => void
  onConnected: () => void
  editDb?: DatabaseInfo | null
}

const DB_TYPES = [
  { value: 'duckdb', label: 'DuckDB' },
  { value: 'sqlite', label: 'SQLite' },
  { value: 'postgres', label: 'PostgreSQL' },
  { value: 'mysql', label: 'MySQL' },
  { value: 'clickhouse', label: 'ClickHouse' },
  { value: 'snowflake', label: 'Snowflake' },
]

const emptyForm = (): DBConnectRequest => ({
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

export default function DBConnectModal({ open, onClose, onConnected, editDb }: DBConnectModalProps) {
  const { t } = useTranslation()
  const [form, setForm] = useState<DBConnectRequest>(emptyForm())
  const [includeText, setIncludeText] = useState('')
  const [excludeText, setExcludeText] = useState('')
  const [testing, setTesting] = useState(false)
  const [connecting, setConnecting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null)
  const [error, setError] = useState('')

  const isEditing = !!editDb

  useEffect(() => {
    if (editDb) {
      setForm({
        name: editDb.name || '',
        type: editDb.type || 'duckdb',
        path: editDb.path || '',
        host: editDb.host || '',
        port: editDb.port || 5432,
        user: editDb.user || '',
        password: editDb.password || '',
        database: editDb.database || '',
        connection_string: editDb.connection_string || '',
        include_tables: editDb.include_tables || [],
        exclude_tables: editDb.exclude_tables || [],
      })
      setIncludeText((editDb.include_tables || []).join(', '))
      setExcludeText((editDb.exclude_tables || []).join(', '))
    } else {
      setForm(emptyForm())
      setIncludeText('')
      setExcludeText('')
    }
    setTestResult(null)
    setError('')
  }, [editDb, open])

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
    if (!form.name.trim()) { setError(t('dbConnect.nameRequired')); return }
    setConnecting(true)
    setError('')
    try {
      const payload = {
        ...form,
        include_tables: includeText.split(',').map(s => s.trim()).filter(Boolean),
        exclude_tables: excludeText.split(',').map(s => s.trim()).filter(Boolean),
      }
      if (isEditing && editDb) {
        await api.updateDatabaseConnection(editDb.id, payload)
      } else {
        await api.connectDatabase(payload)
      }
      onConnected()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setConnecting(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={isEditing ? t('dbConnect.editTitle') : t('dbConnect.addTitle')}
      footer={
        <div className="flex justify-end gap-3 w-full">
          <button onClick={onClose} className="h-9 px-4 text-sm text-gray-600 hover:bg-gray-50 border border-gray-200 rounded-md transition-colors">
            {t('common.cancel')}
          </button>
          <button
            onClick={handleTest}
            disabled={testing}
            className="h-9 px-4 text-sm text-gray-600 hover:bg-gray-50 border border-gray-200 rounded-md transition-colors disabled:opacity-40"
          >
            {testing ? t('common.testing') : t('common.test')}
          </button>
          <button
            onClick={handleConnect}
            disabled={connecting}
            className="h-9 px-4 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-40 transition-colors"
          >
            {connecting ? t('common.saving') : isEditing ? t('dbConnect.saveModify') : t('dbConnect.saveAndConnect')}
          </button>
        </div>
      }
    >
      <div className="space-y-4">
          {/* 数据库类型 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t('dbConnect.dbType')}</label>
            <select
              value={form.type}
              onChange={e => setForm({ ...form, type: e.target.value })}
              className="w-full h-9 px-3 text-sm bg-white border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            >
              {DB_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>

          {/* 名称 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t('dbConnect.name')}</label>
            <input
              className="w-full h-9 px-3 text-sm bg-white border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              placeholder={t('dbConnect.namePlaceholder')}
              value={form.name}
              onChange={e => setForm({ ...form, name: e.target.value })}
            />
          </div>

          {/* 路径 (本地) */}
          {isLocal && (
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t('dbConnect.filePath')}</label>
              <input
                className="w-full h-9 px-3 text-sm bg-white border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
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
                  <label className="block text-xs text-gray-500 mb-1">{t('dbConnect.host')}</label>
                  <input className="w-full h-9 px-3 text-sm bg-white border border-gray-200 rounded-md focus:outline-none" value={form.host} onChange={e => setForm({ ...form, host: e.target.value })} />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">{t('dbConnect.port')}</label>
                  <input type="number" className="w-full h-9 px-3 text-sm bg-white border border-gray-200 rounded-md focus:outline-none" value={form.port} onChange={e => setForm({ ...form, port: Number(e.target.value) })} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">{t('dbConnect.username')}</label>
                  <input className="w-full h-9 px-3 text-sm bg-white border border-gray-200 rounded-md focus:outline-none" value={form.user} onChange={e => setForm({ ...form, user: e.target.value })} />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">{t('dbConnect.password')}</label>
                  <input type="password" autoComplete="off" className="w-full h-9 px-3 text-sm bg-white border border-gray-200 rounded-md focus:outline-none" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t('dbConnect.dbName')}</label>
                <input className="w-full h-9 px-3 text-sm bg-white border border-gray-200 rounded-md focus:outline-none" value={form.database} onChange={e => setForm({ ...form, database: e.target.value })} />
              </div>
            </>
          )}

          {/* 连接字符串 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t('dbConnect.connString')}</label>
            <input
              className="w-full h-9 px-3 text-sm bg-white border border-gray-200 rounded-md focus:outline-none"
              value={form.connection_string}
              onChange={e => setForm({ ...form, connection_string: e.target.value })}
            />
          </div>

          {/* 表过滤 */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t('dbConnect.includeTables')}</label>
              <input
                className="w-full h-9 px-3 text-sm bg-white border border-gray-200 rounded-md focus:outline-none"
                placeholder="fct_*, dim_*"
                value={includeText}
                onChange={e => setIncludeText(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t('dbConnect.excludeTables')}</label>
              <input
                className="w-full h-9 px-3 text-sm bg-white border border-gray-200 rounded-md focus:outline-none"
                placeholder="temp_*"
                value={excludeText}
                onChange={e => setExcludeText(e.target.value)}
              />
            </div>
          </div>

          {/* 测试结果 */}
          {testResult && (
            <div className={`p-3 text-sm rounded-md ${testResult.ok ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
              {testResult.ok ? '✅ ' : '❌ '}{testResult.message}
            </div>
          )}

          {/* 错误 */}
          {error && (
            <div className="p-3 text-sm rounded-md bg-red-50 text-red-700 border border-red-200">
              {error}
            </div>
          )}
        </div>
      </Modal>
  )
}
