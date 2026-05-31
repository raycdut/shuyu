import { useState, useCallback } from 'react'
import { api } from '../../../api'
import type { SystemConfig, LLMModelInstance } from '../../../types'
import { ToggleRow } from '../../../components/AdminSettings/Common'

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
 * LLM 模型实例管理标签页
 */
export function LLMSettingsTab({ config, onSave, saving }: { config: SystemConfig; onSave: (p: Partial<SystemConfig>) => void; saving: boolean }) {
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

      <div className="bg-white/40 p-6 rounded-sm border border-tea/30">
        <h4 className="text-xs font-bold text-ink-lighter uppercase tracking-widest mb-4">全局策略</h4>
        <div className="max-w-md">
          <ToggleRow label="允许用户在个人设置中选择默认模型" checked={allowUserConfig} onChange={setAllowUserConfig} />
        </div>
      </div>

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
