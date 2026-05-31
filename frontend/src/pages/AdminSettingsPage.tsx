import { useState, useEffect } from 'react'
import { api } from '../api'
import type { SystemConfig, UserInfo, ConfigChangeLogEntry } from '../types'

type AdminTab = 'llm' | 'safety' | 'storage' | 'database' | 'users' | 'advanced' | 'logs'

const TABS: { key: AdminTab; label: string }[] = [
  { key: 'llm', label: 'LLM 提供商' },
  { key: 'safety', label: '安全设置' },
  { key: 'storage', label: '存储设置' },
  { key: 'database', label: '数据库管理' },
  { key: 'users', label: '用户管理' },
  { key: 'advanced', label: '高级设置' },
  { key: 'logs', label: '配置日志' },
]

export default function AdminSettingsPage() {
  const [activeTab, setActiveTab] = useState<AdminTab>('llm')
  const [config, setConfig] = useState<SystemConfig | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.getSystemConfig().then(setConfig)
  }, [])

  const handleSave = async (patch: Partial<SystemConfig>) => {
    if (!config) return
    setSaving(true)
    try {
      const updated = await api.updateSystemConfig(patch)
      setConfig(updated)
    } catch (e: any) {
      alert('保存失败: ' + e.message)
    }
    setSaving(false)
  }

  if (!config) {
    return <div className="min-h-screen flex items-center justify-center bg-paper-light"><p className="text-ink-lighter font-kai">加载中…</p></div>
  }

  return (
    <div className="min-h-screen flex bg-paper-light">
      <nav className="w-48 flex-shrink-0 bg-white/60 border-r border-tea py-6">
        <div className="px-4 mb-4">
          <h2 className="text-sm font-song font-semibold text-ink tracking-wider">系统设置</h2>
        </div>
        {TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`w-full text-left px-4 py-2 text-sm transition-colors font-kai ${
              activeTab === tab.key
                ? 'bg-celadon/10 text-celadon-dark border-r-2 border-celadon'
                : 'text-ink-light hover:bg-smoke'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === 'llm' && <LLMSettingsTab config={config} onSave={handleSave} saving={saving} />}
        {activeTab === 'safety' && <SafetySettingsTab config={config} onSave={handleSave} saving={saving} />}
        {activeTab === 'storage' && <StorageSettingsTab config={config} onSave={handleSave} saving={saving} />}
        {activeTab === 'database' && <DatabasePlaceholder />}
        {activeTab === 'users' && <UserManagementTab />}
        {activeTab === 'advanced' && <AdvancedSettingsTab config={config} onSave={handleSave} saving={saving} />}
        {activeTab === 'logs' && <ConfigLogTab />}
      </div>
    </div>
  )
}

function SettingSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <label className="block text-xs text-ink-lighter mb-1.5 font-kai">{title}</label>
      {children}
    </div>
  )
}

function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center gap-3 mb-3">
      <button
        onClick={() => onChange(!checked)}
        className={`w-4 h-4 flex-shrink-0 rounded-sm border transition-colors ${
          checked ? 'bg-celadon border-celadon text-white' : 'bg-white border-tea'
        }`}
      >
        {checked && (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        )}
      </button>
      <span className="text-sm text-ink">{label}</span>
    </div>
  )
}

// === Tab 1: LLM 提供商 ===
function LLMSettingsTab({ config, onSave, saving }: { config: SystemConfig; onSave: (p: Partial<SystemConfig>) => void; saving: boolean }) {
  const [pool, setPool] = useState(config.llm.provider_pool)
  const [defaultModel, setDefaultModel] = useState(config.llm.default_model)
  const [allowUserConfig, setAllowUserConfig] = useState(config.advanced.allow_user_llm_config)

  const handleToggleProvider = (idx: number) => {
    const next = [...pool]
    next[idx] = { ...next[idx], enabled: !next[idx].enabled }
    setPool(next)
  }

  const handleSave = () => {
    onSave({ llm: { provider_pool: pool, default_model: defaultModel }, advanced: { ...config.advanced, allow_user_llm_config: allowUserConfig } })
  }

  return (
    <div>
      <h3 className="text-base font-song font-semibold text-ink mb-4">LLM 提供商池</h3>
      {pool.map((p, i) => (
        <div key={p.provider} className="flex items-center gap-3 mb-3 p-3 bg-white rounded-sm ink-border">
          <button onClick={() => handleToggleProvider(i)} className={`w-4 h-4 flex-shrink-0 rounded-sm border transition-colors ${p.enabled ? 'bg-celadon border-celadon text-white' : 'bg-white border-tea'}`}>
            {p.enabled && <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="20 6 9 17 4 12" /></svg>}
          </button>
          <span className="text-sm text-ink w-24">{p.label}</span>
          <span className="text-xs text-ink-lighter flex-1">{p.models.join(', ')}</span>
          <span className={`text-xs ${p.enabled ? 'text-celadon-dark' : 'text-ink-lighter'}`}>{p.enabled ? '已启用' : '已禁用'}</span>
        </div>
      ))}
      <SettingSection title="系统默认模型">
        <select value={defaultModel} onChange={e => setDefaultModel(e.target.value)} className="ink-input text-sm w-full">
          {pool.filter(p => p.enabled).flatMap(p => p.models.map(m => (
            <option key={m} value={m}>{m}</option>
          )))}
        </select>
      </SettingSection>
      <div className="ink-divider my-4" />
      <h3 className="text-xs text-ink-lighter font-kai tracking-wider mb-3">用户 LLM 权限</h3>
      <ToggleRow label="允许用户自选 LLM 提供商" checked={allowUserConfig} onChange={setAllowUserConfig} />
      <button onClick={handleSave} disabled={saving} className="btn-celadon mt-4">{saving ? '保存中…' : '保存更改'}</button>
    </div>
  )
}

// === Tab 2: 安全设置 ===
function SafetySettingsTab({ config, onSave, saving }: { config: SystemConfig; onSave: (p: Partial<SystemConfig>) => void; saving: boolean }) {
  const [readOnly, setReadOnly] = useState(config.safety.read_only)
  const [requireApproval, setRequireApproval] = useState(config.safety.require_approval)
  const [maxRows, setMaxRows] = useState(config.safety.max_rows)
  const [blockedText, setBlockedText] = useState((config.safety.blocked_tables || []).join(', '))
  const [allowOverride, setAllowOverride] = useState(config.advanced.allow_user_safety_override)

  const handleSave = () => {
    onSave({
      safety: { read_only: readOnly, require_approval: requireApproval, max_rows: maxRows, blocked_tables: blockedText.split(',').map(s => s.trim()).filter(Boolean), masked_columns: config.safety.masked_columns },
      advanced: { ...config.advanced, allow_user_safety_override: allowOverride },
    })
  }

  return (
    <div>
      <h3 className="text-base font-song font-semibold text-ink mb-4">全局安全设置</h3>
      <ToggleRow label="只读模式" checked={readOnly} onChange={setReadOnly} />
      <ToggleRow label="数据确认" checked={requireApproval} onChange={setRequireApproval} />
      <SettingSection title="每页最多行数">
        <input type="number" value={maxRows} onChange={e => setMaxRows(Number(e.target.value))} className="ink-input text-sm" min={10} max={10000} />
      </SettingSection>
      <SettingSection title="全局屏蔽表">
        <input value={blockedText} onChange={e => setBlockedText(e.target.value)} className="ink-input text-sm" placeholder="employee_salary, pii_data" />
      </SettingSection>
      <div className="ink-divider my-4" />
      <h3 className="text-xs text-ink-lighter font-kai tracking-wider mb-3">用户覆盖权限</h3>
      <ToggleRow label="允许用户覆盖安全设置" checked={allowOverride} onChange={setAllowOverride} />
      <button onClick={handleSave} disabled={saving} className="btn-celadon mt-4">{saving ? '保存中…' : '保存更改'}</button>
    </div>
  )
}

// === Tab 3: 存储设置 ===
function StorageSettingsTab({ config, onSave, saving }: { config: SystemConfig; onSave: (p: Partial<SystemConfig>) => void; saving: boolean }) {
  const [logInterval, setLogInterval] = useState(config.storage.log_interval)
  const [retention, setRetention] = useState(config.storage.log_retention_days)

  return (
    <div>
      <h3 className="text-base font-song font-semibold text-ink mb-4">存储设置</h3>
      <SettingSection title="日志存储周期">
        <select value={logInterval} onChange={e => setLogInterval(e.target.value)} className="ink-input text-sm">
          <option value="day">每天</option>
          <option value="hour">每小时</option>
        </select>
      </SettingSection>
      <SettingSection title="日志保留天数">
        <input type="number" value={retention} onChange={e => setRetention(Number(e.target.value))} className="ink-input text-sm" min={1} max={365} />
      </SettingSection>
      <button onClick={() => onSave({ storage: { log_interval: logInterval, log_retention_days: retention } })} disabled={saving} className="btn-celadon mt-4">{saving ? '保存中…' : '保存更改'}</button>
    </div>
  )
}

// === Tab 4: 数据库管理（占位） ===
function DatabasePlaceholder() {
  return (
    <div className="text-center py-16">
      <p className="text-ink-lighter font-kai text-sm mb-2">🗄️ 数据库管理</p>
      <p className="text-ink-lighter font-kai text-xs">此功能正在设计中，敬请期待</p>
    </div>
  )
}

// === Tab 5: 用户管理 ===
function UserManagementTab() {
  const [users, setUsers] = useState<UserInfo[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getUsers().then(setUsers).finally(() => setLoading(false))
  }, [])

  const handleRoleChange = async (u: UserInfo, role: string) => {
    await api.updateUser(u.id, { role })
    setUsers(users.map(user => user.id === u.id ? { ...user, role: role as 'admin' | 'user' } : user))
  }

  const handleToggleActive = async (u: UserInfo) => {
    await api.updateUser(u.id, { is_active: !u.is_active })
    setUsers(users.map(user => user.id === u.id ? { ...user, is_active: !user.is_active } : user))
  }

  const handleDelete = async (u: UserInfo) => {
    if (!confirm(`确定删除用户 ${u.username}？`)) return
    await api.deleteUser(u.id)
    setUsers(users.filter(user => user.id !== u.id))
  }

  if (loading) return <p className="text-ink-lighter font-kai">加载中…</p>

  return (
    <div>
      <h3 className="text-base font-song font-semibold text-ink mb-4">用户管理</h3>
      <div className="bg-white rounded-sm ink-border overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-smoke/50 text-left text-xs text-ink-lighter font-kai">
              <th className="px-4 py-2">用户名</th>
              <th className="px-4 py-2">角色</th>
              <th className="px-4 py-2">状态</th>
              <th className="px-4 py-2">创建时间</th>
              <th className="px-4 py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} className="border-t border-tea/50">
                <td className="px-4 py-2 text-ink">{u.username}</td>
                <td className="px-4 py-2">
                  <select
                    value={u.role}
                    onChange={e => handleRoleChange(u, e.target.value)}
                    className="ink-input text-xs"
                  >
                    <option value="user">用户</option>
                    <option value="admin">管理员</option>
                  </select>
                </td>
                <td className="px-4 py-2">
                  <span className={`text-xs ${u.is_active ? 'text-celadon-dark' : 'text-ink-lighter'}`}>
                    {u.is_active ? '已启用' : '已禁用'}
                  </span>
                </td>
                <td className="px-4 py-2 text-xs text-ink-lighter">
                  {u.created_at ? new Date(u.created_at).toLocaleDateString() : '-'}
                </td>
                <td className="px-4 py-2 flex gap-2">
                  <button onClick={() => handleToggleActive(u)} className="text-xs text-ink-lighter hover:text-celadon-dark transition-colors">
                    {u.is_active ? '禁用' : '启用'}
                  </button>
                  <button onClick={() => handleDelete(u)} className="text-xs text-ink-lighter hover:text-cinnabar transition-colors">
                    删除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// === Tab 6: 高级设置 ===
function AdvancedSettingsTab({ config, onSave, saving }: { config: SystemConfig; onSave: (p: Partial<SystemConfig>) => void; saving: boolean }) {
  const [expire, setExpire] = useState(config.advanced.session_expire_minutes)
  const [maxSessions, setMaxSessions] = useState(config.advanced.max_sessions_per_user)
  const [tempMin, setTempMin] = useState(config.advanced.llm_temperature_range.min)
  const [tempMax, setTempMax] = useState(config.advanced.llm_temperature_range.max)
  const [tempDefault, setTempDefault] = useState(config.advanced.llm_temperature_range.default)

  return (
    <div>
      <h3 className="text-base font-song font-semibold text-ink mb-4">高级设置</h3>
      <SettingSection title="会话过期时间（分钟）">
        <input type="number" value={expire} onChange={e => setExpire(Number(e.target.value))} className="ink-input text-sm" min={5} max={43200} />
      </SettingSection>
      <SettingSection title="每用户最大会话数">
        <input type="number" value={maxSessions} onChange={e => setMaxSessions(Number(e.target.value))} className="ink-input text-sm" min={1} max={500} />
      </SettingSection>
      <SettingSection title="温度范围 - 最小值">
        <input type="number" value={tempMin} onChange={e => setTempMin(Number(e.target.value))} className="ink-input text-sm" min={0} max={1} step={0.1} />
      </SettingSection>
      <SettingSection title="温度范围 - 最大值">
        <input type="number" value={tempMax} onChange={e => setTempMax(Number(e.target.value))} className="ink-input text-sm" min={0} max={2} step={0.1} />
      </SettingSection>
      <SettingSection title="温度范围 - 默认值">
        <input type="number" value={tempDefault} onChange={e => setTempDefault(Number(e.target.value))} className="ink-input text-sm" min={0} max={1} step={0.1} />
      </SettingSection>
      <button onClick={() => onSave({ advanced: { session_expire_minutes: expire, max_sessions_per_user: maxSessions, llm_temperature_range: { min: tempMin, max: tempMax, default: tempDefault }, allow_user_llm_config: config.advanced.allow_user_llm_config, allow_user_safety_override: config.advanced.allow_user_safety_override } })} disabled={saving} className="btn-celadon mt-4">{saving ? '保存中…' : '保存更改'}</button>
    </div>
  )
}

// === Tab 7: 配置日志 ===
function ConfigLogTab() {
  const [logs, setLogs] = useState<ConfigChangeLogEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getConfigChangelog().then(setLogs).finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-ink-lighter font-kai">加载中…</p>

  return (
    <div>
      <h3 className="text-base font-song font-semibold text-ink mb-4">配置变更日志</h3>
      <div className="bg-white rounded-sm ink-border overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-smoke/50 text-left text-xs text-ink-lighter font-kai">
              <th className="px-4 py-2">时间</th>
              <th className="px-4 py-2">操作人</th>
              <th className="px-4 py-2">变更摘要</th>
            </tr>
          </thead>
          <tbody>
            {logs.map(log => (
              <tr key={log.id} className="border-t border-tea/50">
                <td className="px-4 py-2 text-xs text-ink-lighter">{new Date(log.created_at).toLocaleString()}</td>
                <td className="px-4 py-2 text-xs text-ink">{log.changed_by}</td>
                <td className="px-4 py-2 text-sm text-ink">{log.summary}</td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr><td colSpan={3} className="px-4 py-8 text-center text-ink-lighter font-kai text-xs">暂无变更记录</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
