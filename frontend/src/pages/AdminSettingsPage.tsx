import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import type { SystemConfig, UserInfo, ConfigChangeLogEntry, LLMModelInstance } from '../types'

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

/**
 * 管理后台主页面，采用左栏导航+右栏工作区的布局
 */
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
    <div className="flex-1 flex bg-paper-light overflow-hidden w-full">
      <nav className="w-56 flex-shrink-0 bg-white/60 border-r border-tea py-6 shadow-sm z-10">
        <div className="px-6 mb-6">
          <h2 className="text-xs font-song font-bold text-ink-lighter uppercase tracking-widest">系统管理</h2>
        </div>
        <div className="space-y-1">
          {TABS.map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`w-full text-left px-6 py-3 text-sm transition-all duration-200 font-kai flex items-center gap-3 ${
                activeTab === tab.key
                  ? 'bg-celadon text-white shadow-md'
                  : 'text-ink-light hover:bg-smoke hover:pl-7'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${activeTab === tab.key ? 'bg-white' : 'bg-tea/40'}`} />
              {tab.label}
            </button>
          ))}
        </div>
      </nav>

      <main className="flex-1 overflow-y-auto bg-paper-light/30">
        <div className="w-full h-full min-w-[600px] p-8 lg:p-12">
          <div className="max-w-6xl mx-auto">
            {activeTab === 'llm' && <LLMSettingsTab config={config} onSave={handleSave} saving={saving} />}
            {activeTab === 'safety' && <SafetySettingsTab config={config} onSave={handleSave} saving={saving} />}
            {activeTab === 'storage' && <StorageSettingsTab config={config} onSave={handleSave} saving={saving} />}
            {activeTab === 'database' && <DatabasePlaceholder />}
            {activeTab === 'users' && <UserManagementTab />}
            {activeTab === 'advanced' && <AdvancedSettingsTab config={config} onSave={handleSave} saving={saving} />}
            {activeTab === 'logs' && <ConfigLogTab />}
          </div>
        </div>
      </main>
    </div>
  )
}

/**
 * 设置项容器，包含标签和子组件
 */
function SettingSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-6 w-full">
      <label className="block text-xs text-ink-lighter mb-2 font-kai tracking-wide">{title}</label>
      <div className="w-full">
        {children}
      </div>
    </div>
  )
}

/**
 * 开关行组件，用于布尔设置
 */
function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div 
      className="flex items-center justify-between p-3 rounded-sm hover:bg-smoke/50 transition-colors cursor-pointer border border-transparent hover:border-tea/30"
      onClick={() => onChange(!checked)}
    >
      <span className="text-sm text-ink font-kai">{label}</span>
      <button
        className={`w-10 h-5 flex items-center rounded-full p-1 transition-colors duration-200 ${
          checked ? 'bg-celadon' : 'bg-tea/30'
        }`}
      >
        <div className={`bg-white w-3 h-3 rounded-full shadow-sm transition-transform duration-200 ${checked ? 'translate-x-5' : 'translate-x-0'}`} />
      </button>
    </div>
  )
}

/**
 * LLM 模型实例管理标签页
 * 支持模型实例的列表展示、新增/编辑、连通性测试、设置默认、删除
 */
function LLMSettingsTab({ config, onSave, saving }: { config: SystemConfig; onSave: (p: Partial<SystemConfig>) => void; saving: boolean }) {
  const [models, setModels] = useState<LLMModelInstance[]>(config.llm.models || [])
  const [allowUserConfig, setAllowUserConfig] = useState(config.advanced.allow_user_llm_config)
  const [showDialog, setShowDialog] = useState(false)
  const [editingModel, setEditingModel] = useState<LLMModelInstance | null>(null)
  const [testingIds, setTestingIds] = useState<Set<string>>(new Set())
  const [connectionStatuses, setConnectionStatuses] = useState<Record<string, { ok: boolean; message: string }>>({})

  const PROVIDER_OPTIONS = [
    { value: 'openai', label: 'OpenAI', defaultBase: 'https://api.openai.com/v1' },
    { value: 'deepseek', label: 'DeepSeek', defaultBase: 'https://api.deepseek.com/v1' },
    { value: 'azure', label: 'Azure OpenAI', defaultBase: '' },
    { value: 'anthropic', label: 'Anthropic', defaultBase: 'https://api.anthropic.com/v1' },
    { value: 'ollama', label: 'Ollama', defaultBase: 'http://localhost:11434/v1' },
    { value: 'custom', label: '自定义', defaultBase: '' },
  ]

  const getProviderInfo = (provider: string) => PROVIDER_OPTIONS.find(p => p.value === provider) || PROVIDER_OPTIONS[PROVIDER_OPTIONS.length - 1]

  const handleTestConnection = useCallback(async (model: LLMModelInstance) => {
    setTestingIds(prev => new Set(prev).add(model.id))
    setConnectionStatuses(prev => ({ ...prev, [model.id]: { ok: false, message: '测试中…' } }))
    try {
      // Send model_id so backend can look up the real (unmasked) API key
      const result = await api.testLLM({
        model_id: model.id,
      })
      setConnectionStatuses(prev => ({ ...prev, [model.id]: result }))
    } catch (e: any) {
      setConnectionStatuses(prev => ({ ...prev, [model.id]: { ok: false, message: e.message } }))
    }
    setTestingIds(prev => {
      const next = new Set(prev)
      next.delete(model.id)
      return next
    })
  }, [])

  const handleSetDefault = (id: string) => {
    setModels(prev => prev.map(m => ({
      ...m,
      is_system_default: m.id === id,
    })))
  }

  const handleToggleEnabled = (id: string) => {
    setModels(prev => prev.map(m => {
      if (m.id !== id) return m
      return { ...m, enabled: !m.enabled }
    }))
  }

  const handleDelete = (id: string) => {
    const target = models.find(m => m.id === id)
    if (!target) return
    if (target.is_system_default) {
      if (!confirm('此模型是系统默认模型，删除后将自动选择其他可用模型作为默认。确定删除？')) return
    } else {
      if (!confirm(`确定删除模型「${target.name}」？`)) return
    }
    setModels(prev => prev.filter(m => m.id !== id))
  }

  const handleOpenAdd = () => {
    setEditingModel(null)
    setShowDialog(true)
  }

  const handleOpenEdit = (model: LLMModelInstance) => {
    setEditingModel(model)
    setShowDialog(true)
  }

  const handleSaveDialog = (model: LLMModelInstance) => {
    if (editingModel) {
      setModels(prev => prev.map(m => m.id === model.id ? model : m))
    } else {
      setModels(prev => [...prev, model])
    }
    setShowDialog(false)
    setEditingModel(null)
  }

  const handleSaveAll = () => {
    onSave({
      llm: { models },
      advanced: { ...config.advanced, allow_user_llm_config: allowUserConfig },
    })
  }

  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="flex items-center justify-between mb-8 border-b border-tea pb-4">
        <div>
          <h3 className="text-xl font-song font-bold text-ink">LLM 模型管理</h3>
          <p className="text-xs text-ink-lighter font-kai mt-1">管理已配置的大模型实例，支持添加、编辑、连通性测试和默认模型设置</p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={handleOpenAdd} className="btn-celadon-outline px-4 py-2 text-sm shadow-sm flex items-center gap-1.5">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            添加模型
          </button>
          <button onClick={handleSaveAll} disabled={saving} className="btn-celadon px-4 py-2 text-sm shadow-sm">
            {saving ? '保存中…' : '保存更改'}
          </button>
        </div>
      </div>

      {/* Model Cards Grid */}
      <div className="grid grid-cols-1 gap-4 mb-8">
        {models.length === 0 && (
          <div className="col-span-full flex flex-col items-center justify-center py-16 border-2 border-dashed border-tea/30 rounded-lg bg-smoke/20">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-tea mb-3">
              <rect x="4" y="4" width="16" height="16" rx="2" />
              <path d="M9 9h.01M15 9h.01M9 15h6" />
            </svg>
            <p className="text-sm text-ink-lighter font-kai mb-1">暂无配置的模型</p>
            <button onClick={handleOpenAdd} className="text-xs text-celadon-dark hover:underline font-kai">点击添加第一个模型</button>
          </div>
        )}
        {models.map(m => {
           const providerInfo = getProviderInfo(m.provider)
           const isTesting = testingIds.has(m.id)
           const status = connectionStatuses[m.id]
          return (
            <div
              key={m.id}
              className={`relative flex items-start gap-4 p-5 bg-white rounded-sm border transition-all ${
                m.enabled ? 'border-tea/40 shadow-sm hover:shadow-md' : 'border-tea/20 opacity-55'
              }`}
            >
              {/* Enabled Toggle */}
              <button
                onClick={() => handleToggleEnabled(m.id)}
                className={`mt-0.5 w-5 h-5 flex-shrink-0 rounded-sm border transition-colors flex items-center justify-center ${
                  m.enabled ? 'bg-celadon border-celadon text-white' : 'bg-white border-tea'
                }`}
              >
                {m.enabled && (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="4" className="w-3 h-3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
              </button>

              {/* Model Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-semibold text-ink truncate">{m.name}</span>
                  {m.is_system_default && (
                    <span className="flex-shrink-0 px-1.5 py-0.5 bg-celadon/10 text-celadon-dark text-[10px] font-bold rounded-sm border border-celadon/20">
                      默认
                    </span>
                  )}
                  <span className="flex-shrink-0 bg-smoke px-1.5 py-0.5 text-[10px] text-ink-light rounded-full border border-tea/20 font-mono">
                     {providerInfo?.label || m.provider}/{m.model}
                   </span>
                </div>
                {/* Connection Status */}
                <div className="flex items-center gap-2 mt-1">
                  {status ? (
                    <span className={`flex items-center gap-1 text-[10px] ${status.ok ? 'text-green-600' : 'text-cinnabar'}`}>
                      <span className={`inline-block w-1.5 h-1.5 rounded-full ${status.ok ? 'bg-green-500' : 'bg-cinnabar'}`} />
                      {status.ok ? '连接正常' : `连接失败: ${status.message.slice(0, 50)}`}
                    </span>
                  ) : (
                    <span className="text-[10px] text-ink-lighter flex items-center gap-1">
                      <span className="inline-block w-1.5 h-1.5 rounded-full bg-ink-lighter/30" />
                      未检测
                    </span>
                  )}
                  {m.api_key && (
                    <span className="text-[10px] text-ink-lighter font-mono">
                      API Key: {m.api_key.slice(0, 8)}••••
                    </span>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-1.5 flex-shrink-0">
                <button
                  onClick={() => handleTestConnection(m)}
                  disabled={isTesting}
                  className={`px-2.5 py-1 text-[10px] rounded-sm border transition-colors font-kai ${
                    isTesting
                      ? 'bg-smoke text-ink-lighter border-tea/30 cursor-wait'
                      : 'bg-white text-ink-light border-tea/40 hover:bg-celadon/5 hover:border-celadon/40'
                  }`}
                >
                  {isTesting ? '检测中…' : '测试'}
                </button>
                {!m.is_system_default && m.enabled && (
                  <button
                    onClick={() => handleSetDefault(m.id)}
                    className="px-2.5 py-1 text-[10px] rounded-sm border border-tea/40 bg-white text-ink-light hover:bg-amber/5 hover:border-amber/40 transition-colors font-kai"
                  >
                    设为默认
                  </button>
                )}
                <button
                  onClick={() => handleOpenEdit(m)}
                  className="px-2.5 py-1 text-[10px] rounded-sm border border-tea/40 bg-white text-ink-light hover:bg-celadon/5 hover:border-celadon/40 transition-colors font-kai"
                >
                  编辑
                </button>
                <button
                  onClick={() => handleDelete(m.id)}
                  className="px-2.5 py-1 text-[10px] rounded-sm border border-tea/40 bg-white text-cinnabar/70 hover:bg-cinnabar/5 hover:border-cinnabar/40 transition-colors font-kai"
                >
                  删除
                </button>
              </div>
            </div>
          )
        })}
      </div>

      {/* Global Strategy Section */}
      <div className="bg-white/40 p-6 rounded-sm border border-tea/30">
        <h4 className="text-xs font-bold text-ink-lighter uppercase tracking-widest mb-4">全局策略</h4>
        <div className="max-w-md">
          <ToggleRow label="允许用户在个人设置中选择默认模型" checked={allowUserConfig} onChange={setAllowUserConfig} />
        </div>
      </div>

      {/* Add/Edit Dialog */}
      {showDialog && (
        <ModelDialog
           model={editingModel}
           providerOptions={PROVIDER_OPTIONS}
           onSave={handleSaveDialog}
           onClose={() => { setShowDialog(false); setEditingModel(null) }}
         />
      )}
    </div>
  )
}

/**
 * 模型新增/编辑对话框
 */
function ModelDialog({
  model,
  providerOptions,
  onSave,
  onClose,
}: {
  model: LLMModelInstance | null
  providerOptions: { value: string; label: string; defaultBase: string }[]
  onSave: (m: LLMModelInstance) => void
  onClose: () => void
}) {
  const [name, setName] = useState(model?.name || '')
  const [provider, setProvider] = useState(model?.provider || 'openai')
  const [modelId, setModelId] = useState(model?.model || '')
  const [apiKey, setApiKey] = useState(model?.api_key || '')
  const [apiBase, setApiBase] = useState(model?.api_base || '')
  const [timeout, setTimeout_] = useState(model?.timeout || 120)

  const providerInfo = providerOptions.find(p => p.value === provider)
  const isCustomProvider = provider === 'custom'

  const handleProviderChange = (val: string) => {
    setProvider(val)
    const info = providerOptions.find(p => p.value === val)
    if (info?.defaultBase && !apiBase) {
      setApiBase(info.defaultBase)
    }
    if (val === 'custom') {
      setApiBase('')
    }
  }

  const generateId = () => 'model_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6)

  const handleSave = () => {
    if (!name.trim()) { alert('请输入模型名称'); return }
    if (!modelId.trim()) { alert('请输入模型 ID'); return }
    const instance: LLMModelInstance = {
      id: model?.id || generateId(),
      name: name.trim(),
      provider,
      model: modelId.trim(),
      api_key: apiKey,
      api_base: apiBase,
      timeout,
      enabled: model?.enabled ?? true,
      is_system_default: model?.is_system_default ?? false,
    }
    onSave(instance)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-xl border border-tea/30 w-full max-w-lg mx-4 p-6 animate-in fade-in zoom-in-95 duration-200" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h4 className="text-base font-song font-bold text-ink">{model ? '编辑模型' : '添加模型'}</h4>
          <button onClick={onClose} className="p-1 text-ink-lighter hover:text-ink transition-colors rounded-sm hover:bg-smoke">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-ink-lighter mb-1 font-kai">显示名称</label>
              <input value={name} onChange={e => setName(e.target.value)} className="ink-input w-full" placeholder="例: 生产环境 GPT-4o" />
            </div>
            <div>
              <label className="block text-xs text-ink-lighter mb-1 font-kai">供应商</label>
              <select value={provider} onChange={e => handleProviderChange(e.target.value)} className="ink-input w-full">
                {providerOptions.map(p => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
          </div>

          {isCustomProvider && (
            <div>
              <label className="block text-xs text-ink-lighter mb-1 font-kai">自定义供应商标识</label>
              <input value={provider} onChange={e => setProvider(e.target.value)} className="ink-input w-full" placeholder="例: together" />
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-ink-lighter mb-1 font-kai">模型 ID</label>
              <input value={modelId} onChange={e => setModelId(e.target.value)} className="ink-input w-full" placeholder="例: gpt-4o" />
            </div>
            <div>
              <label className="block text-xs text-ink-lighter mb-1 font-kai">超时时间（秒）</label>
              <input type="number" value={timeout} onChange={e => setTimeout_(Number(e.target.value))} className="ink-input w-full" min={10} max={600} />
            </div>
          </div>

          <div>
            <label className="block text-xs text-ink-lighter mb-1 font-kai">API Base URL <span className="text-ink-lighter/60">（可选）</span></label>
            <input value={apiBase} onChange={e => setApiBase(e.target.value)} className="ink-input w-full font-mono text-xs" placeholder={providerInfo?.defaultBase || 'https://'} />
          </div>

          <div>
            <label className="block text-xs text-ink-lighter mb-1 font-kai">API Key</label>
            <input
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              className="ink-input w-full font-mono text-xs"
              placeholder={model ? '输入新 Key 以覆盖，留空保持不变' : 'sk-...'}
            />
          </div>
        </div>

        <div className="flex items-center justify-end mt-6 pt-4 border-t border-tea/20 gap-2">
          <button onClick={onClose} className="px-4 py-2 text-sm text-ink-light hover:text-ink transition-colors font-kai">
            取消
          </button>
          <button onClick={handleSave} className="btn-celadon px-5 py-2 text-sm shadow-sm font-kai">
            {model ? '保存更改' : '添加模型'}
          </button>
        </div>
      </div>
    </div>
  )
}

/**
 * 安全设置标签页
 */
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
    <div className="w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="flex items-center justify-between mb-8 border-b border-tea pb-4">
        <div>
          <h3 className="text-xl font-song font-bold text-ink">全局安全设置</h3>
          <p className="text-xs text-ink-lighter font-kai mt-1">控制数据访问的只读权限、屏蔽表以及用户覆盖规则</p>
        </div>
        <button onClick={handleSave} disabled={saving} className="btn-celadon px-6 py-2 shadow-sm">{saving ? '保存中…' : '保存所有更改'}</button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
        <div className="space-y-6">
          <h4 className="text-xs font-bold text-ink-lighter uppercase tracking-widest mb-4">访问策略</h4>
          <div className="bg-white/40 p-4 rounded-sm border border-tea/30 space-y-2">
            <ToggleRow label="全局只读模式" checked={readOnly} onChange={setReadOnly} />
            <ToggleRow label="数据确认（敏感操作需人工确认）" checked={requireApproval} onChange={setRequireApproval} />
            <ToggleRow label="允许用户在个人设置中覆盖安全设置" checked={allowOverride} onChange={setAllowOverride} />
          </div>
        </div>

        <div className="space-y-6">
          <h4 className="text-xs font-bold text-ink-lighter uppercase tracking-widest mb-4">数据限制</h4>
          <SettingSection title="单次查询最大返回行数">
            <input type="number" value={maxRows} onChange={e => setMaxRows(Number(e.target.value))} className="ink-input" min={10} max={10000} />
            <p className="text-[10px] text-ink-lighter mt-1.5 font-kai">防止大批量数据导出导致的性能问题</p>
          </SettingSection>
          <SettingSection title="全局屏蔽表（逗号分隔）">
            <input value={blockedText} onChange={e => setBlockedText(e.target.value)} className="ink-input" placeholder="salary, pii_data, internal_audit" />
            <p className="text-[10px] text-ink-lighter mt-1.5 font-kai">被屏蔽的表将对所有非管理员用户不可见</p>
          </SettingSection>
        </div>
      </div>
    </div>
  )
}

/**
 * 存储设置标签页
 */
function StorageSettingsTab({ config, onSave, saving }: { config: SystemConfig; onSave: (p: Partial<SystemConfig>) => void; saving: boolean }) {
  const [logInterval, setLogInterval] = useState(config.storage.log_interval)
  const [retention, setRetention] = useState(config.storage.log_retention_days)

  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="flex items-center justify-between mb-8 border-b border-tea pb-4">
        <div>
          <h3 className="text-xl font-song font-bold text-ink">存储与日志设置</h3>
          <p className="text-xs text-ink-lighter font-kai mt-1">配置系统日志的记录频率与持久化策略</p>
        </div>
        <button onClick={() => onSave({ storage: { log_interval: logInterval, log_retention_days: retention } })} disabled={saving} className="btn-celadon px-6 py-2 shadow-sm">{saving ? '保存中…' : '保存所有更改'}</button>
      </div>

      <div className="max-w-2xl bg-white/40 p-8 rounded-sm border border-tea/30">
        <div className="space-y-8">
          <SettingSection title="日志归档周期">
            <div className="flex gap-4">
              {['hour', 'day'].map(mode => (
                <button
                  key={mode}
                  onClick={() => setLogInterval(mode as any)}
                  className={`flex-1 py-3 px-4 rounded-sm border text-sm font-kai transition-all ${
                    logInterval === mode 
                      ? 'bg-celadon text-white border-celadon shadow-md' 
                      : 'bg-white text-ink-light border-tea hover:border-celadon/50'
                  }`}
                >
                  {mode === 'hour' ? '每小时归档' : '每天归档'}
                </button>
              ))}
            </div>
          </SettingSection>

          <SettingSection title="历史记录保留天数">
            <div className="flex items-center gap-4">
              <input type="range" value={retention} onChange={e => setRetention(Number(e.target.value))} className="flex-1 accent-celadon" min={1} max={365} />
              <div className="w-20 text-center bg-white border border-tea py-2 rounded-sm text-sm font-semibold text-ink">
                {retention} 天
              </div>
            </div>
            <p className="text-[10px] text-ink-lighter mt-2 font-kai">超出此期限的日志将被系统自动清理以节省存储空间</p>
          </SettingSection>
        </div>
      </div>
    </div>
  )
}

/**
 * 数据库管理占位组件
 */
function DatabasePlaceholder() {
  return (
    <div className="w-full h-[400px] flex flex-col items-center justify-center border-2 border-dashed border-tea/30 rounded-lg bg-smoke/20 animate-in fade-in duration-500">
      <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center shadow-sm mb-4 border border-tea/20">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-tea">
          <ellipse cx="12" cy="5" rx="9" ry="3" />
          <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
          <path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3" />
        </svg>
      </div>
      <h3 className="text-lg font-song font-bold text-ink mb-1">数据库管理</h3>
      <p className="text-sm text-ink-lighter font-kai max-w-xs text-center">此功能正在深度设计中，未来将支持多数据库连接池、动态 Schema 刷新与权限审计</p>
    </div>
  )
}

/**
 * 用户管理标签页
 */
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

  if (loading) return <div className="py-12 text-center text-ink-lighter font-kai">加载中…</div>

  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="flex items-center justify-between mb-8 border-b border-tea pb-4">
        <div>
          <h3 className="text-xl font-song font-bold text-ink">用户管理</h3>
          <p className="text-xs text-ink-lighter font-kai mt-1">管理系统访问账号、分配角色权限并控制账号状态</p>
        </div>
      </div>

      <div className="bg-white rounded-sm ink-border shadow-sm overflow-hidden w-full">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-smoke/50 text-left text-xs text-ink-lighter font-kai uppercase tracking-wider">
              <th className="px-6 py-4 font-bold">用户信息</th>
              <th className="px-6 py-4 font-bold">角色权限</th>
              <th className="px-6 py-4 font-bold">账号状态</th>
              <th className="px-6 py-4 font-bold">注册日期</th>
              <th className="px-6 py-4 font-bold text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-tea/20">
            {users.map(u => (
              <tr key={u.id} className="hover:bg-smoke/30 transition-colors">
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-celadon/10 flex items-center justify-center text-celadon-dark font-bold text-xs">
                      {u.username[0].toUpperCase()}
                    </div>
                    <span className="font-medium text-ink">{u.username}</span>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <select
                    value={u.role}
                    onChange={e => handleRoleChange(u, e.target.value)}
                    className="bg-paper-light border border-tea/50 rounded px-2 py-1 text-xs focus:border-celadon outline-none transition-colors"
                  >
                    <option value="user">普通用户</option>
                    <option value="admin">管理员</option>
                  </select>
                </td>
                <td className="px-6 py-4">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${
                    u.is_active ? 'bg-celadon/10 text-celadon-dark' : 'bg-cinnabar/10 text-cinnabar'
                  }`}>
                    {u.is_active ? '正常' : '已禁用'}
                  </span>
                </td>
                <td className="px-6 py-4 text-xs text-ink-lighter font-kai">
                  {u.created_at ? new Date(u.created_at).toLocaleDateString() : '-'}
                </td>
                <td className="px-6 py-4 text-right">
                  <div className="flex justify-end gap-3">
                    <button onClick={() => handleToggleActive(u)} className="text-xs text-celadon-dark hover:underline font-kai">
                      {u.is_active ? '禁用' : '启用'}
                    </button>
                    <button onClick={() => handleDelete(u)} className="text-xs text-cinnabar hover:underline font-kai">
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/**
 * 高级系统设置标签页
 */
function AdvancedSettingsTab({ config, onSave, saving }: { config: SystemConfig; onSave: (p: Partial<SystemConfig>) => void; saving: boolean }) {
  const [expire, setExpire] = useState(config.advanced.session_expire_minutes)
  const [maxSessions, setMaxSessions] = useState(config.advanced.max_sessions_per_user)
  const [tempMin, setTempMin] = useState(config.advanced.llm_temperature_range.min)
  const [tempMax, setTempMax] = useState(config.advanced.llm_temperature_range.max)
  const [tempDefault, setTempDefault] = useState(config.advanced.llm_temperature_range.default)

  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="flex items-center justify-between mb-8 border-b border-tea pb-4">
        <div>
          <h3 className="text-xl font-song font-bold text-ink">高级系统参数</h3>
          <p className="text-xs text-ink-lighter font-kai mt-1">调整系统性能极限、会话生命周期与模型采样参数</p>
        </div>
        <button 
          onClick={() => onSave({ 
            advanced: { 
              session_expire_minutes: expire, 
              max_sessions_per_user: maxSessions, 
              llm_temperature_range: { min: tempMin, max: tempMax, default: tempDefault }, 
              allow_user_llm_config: config.advanced.allow_user_llm_config, 
              allow_user_safety_override: config.advanced.allow_user_safety_override 
            } 
          })} 
          disabled={saving} 
          className="btn-celadon px-6 py-2 shadow-sm"
        >
          {saving ? '保存中…' : '保存所有更改'}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
        <div className="space-y-8 bg-white/40 p-6 rounded-sm border border-tea/30">
          <h4 className="text-xs font-bold text-ink-lighter uppercase tracking-widest mb-4 border-l-2 border-celadon pl-3">会话与性能</h4>
          <SettingSection title="登录会话过期时间（分钟）">
            <input type="number" value={expire} onChange={e => setExpire(Number(e.target.value))} className="ink-input" min={5} max={43200} />
            <p className="text-[10px] text-ink-lighter mt-1 font-kai text-right">30天 = 43200分钟</p>
          </SettingSection>
          <SettingSection title="单用户最大并行会话数">
            <input type="number" value={maxSessions} onChange={e => setMaxSessions(Number(e.target.value))} className="ink-input" min={1} max={500} />
          </SettingSection>
        </div>

        <div className="space-y-8 bg-white/40 p-6 rounded-sm border border-tea/30">
          <h4 className="text-xs font-bold text-ink-lighter uppercase tracking-widest mb-4 border-l-2 border-celadon pl-3">LLM 采样参数限制</h4>
          <div className="grid grid-cols-2 gap-4">
            <SettingSection title="温度最小值">
              <input type="number" value={tempMin} onChange={e => setTempMin(Number(e.target.value))} className="ink-input" min={0} max={1} step={0.1} />
            </SettingSection>
            <SettingSection title="温度最大值">
              <input type="number" value={tempMax} onChange={e => setTempMax(Number(e.target.value))} className="ink-input" min={0} max={2} step={0.1} />
            </SettingSection>
          </div>
          <SettingSection title="系统默认温度 (Temperature)">
            <div className="flex items-center gap-4">
              <input type="range" value={tempDefault} onChange={e => setTempDefault(Number(e.target.value))} className="flex-1 accent-celadon" min={tempMin} max={tempMax} step={0.05} />
              <span className="w-12 text-center text-sm font-bold text-celadon-dark">{tempDefault}</span>
            </div>
            <p className="text-[10px] text-ink-lighter mt-2 font-kai">数值越高输出越具创造性，越低则越严谨</p>
          </SettingSection>
        </div>
      </div>
    </div>
  )
}

/**
 * 配置变更日志标签页
 */
function ConfigLogTab() {
  const [logs, setLogs] = useState<ConfigChangeLogEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getConfigChangelog().then(setLogs).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="py-12 text-center text-ink-lighter font-kai">加载中…</div>

  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="flex items-center justify-between mb-8 border-b border-tea pb-4">
        <div>
          <h3 className="text-xl font-song font-bold text-ink">配置变更审计</h3>
          <p className="text-xs text-ink-lighter font-kai mt-1">追溯系统配置的每一次修改，确保配置变更可审计</p>
        </div>
      </div>

      <div className="bg-white rounded-sm ink-border shadow-sm overflow-hidden w-full">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-smoke/50 text-left text-xs text-ink-lighter font-kai uppercase tracking-wider">
              <th className="px-6 py-4 font-bold w-48">变更时间</th>
              <th className="px-6 py-4 font-bold w-32">操作人</th>
              <th className="px-6 py-4 font-bold">变更摘要</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-tea/20">
            {logs.map(log => (
              <tr key={log.id} className="hover:bg-smoke/10 transition-colors">
                <td className="px-6 py-4 text-xs text-ink-lighter font-mono">
                  {new Date(log.created_at).toLocaleString()}
                </td>
                <td className="px-6 py-4">
                  <span className="text-xs font-semibold text-ink bg-tea/10 px-2 py-0.5 rounded-sm">
                    {log.changed_by}
                  </span>
                </td>
                <td className="px-6 py-4 text-sm text-ink leading-relaxed">
                  {log.summary}
                </td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr>
                <td colSpan={3} className="px-6 py-12 text-center text-ink-lighter font-kai text-sm italic">
                  暂无任何配置变更记录
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
