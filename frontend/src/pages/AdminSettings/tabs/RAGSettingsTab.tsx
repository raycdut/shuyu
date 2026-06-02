import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { SettingSection, ToggleRow, PageHeader } from '../../../components/AdminSettings/Common'
import { useAdminSettings } from '../AdminSettingsContext'

export function RAGSettingsTab() {
  const { t } = useTranslation()
  const { config, saving, save } = useAdminSettings()
  const rag = config.rag || {
    enabled: false,
    provider: 'openai',
    model: 'text-embedding-3-small',
    api_key: '',
    api_base: '',
    top_k: 5,
    min_score: 0.3,
    self_learn: false,
  }

  const [enabled, setEnabled] = useState(rag.enabled)
  const [provider, setProvider] = useState(rag.provider)
  const [model, setModel] = useState(rag.model)
  const [apiKey, setApiKey] = useState(rag.api_key)
  const [apiBase, setApiBase] = useState(rag.api_base)
  const [topK, setTopK] = useState(rag.top_k)
  const [minScore, setMinScore] = useState(rag.min_score)
  const [selfLearn, setSelfLearn] = useState(rag.self_learn)

  const handleSave = () => {
    save({
      rag: {
        enabled,
        provider,
        model,
        api_key: apiKey,
        api_base: apiBase,
        top_k: topK,
        min_score: minScore,
        self_learn: selfLearn,
      },
    })
  }

  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
      <PageHeader
        title="RAG 配置"
        subtitle="语义 Schema 检索 —— 根据用户问题只注入最相关的表结构，减少 Token 消耗"
        actions={<button onClick={handleSave} disabled={saving} className="btn-celadon px-6 py-2 shadow-sm">{saving ? t('common.saving') : t('common.saveAllChanges')}</button>}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
        <div className="space-y-6">
          <h4 className="text-xs font-bold text-ink-lighter uppercase tracking-widest mb-4">开关与自学习</h4>
          <div className="bg-white/40 p-4 rounded-sm border border-tea/30 space-y-2">
            <ToggleRow label="启用 RAG" checked={enabled} onChange={setEnabled} />
            <ToggleRow label="自学习（Phase 5）" checked={selfLearn} onChange={setSelfLearn} />
          </div>
          <p className="text-[10px] text-ink-lighter mt-1.5 font-kai leading-relaxed">
            启用后，系统会根据用户问题的语义只检索最相关的 Top-K 张表，而不是注入全部表结构。
            未启用时行为与现有版本完全一致。
          </p>
        </div>

        <div className="space-y-6">
          <h4 className="text-xs font-bold text-ink-lighter uppercase tracking-widest mb-4">嵌入服务</h4>
          <SettingSection title="Provider">
            <select value={provider} onChange={e => setProvider(e.target.value)} className="ink-input">
              <option value="openai">OpenAI</option>
              <option value="siliconflow">SiliconFlow</option>
            </select>
          </SettingSection>
          <SettingSection title="模型">
            <input value={model} onChange={e => setModel(e.target.value)} className="ink-input" placeholder="text-embedding-3-small" />
          </SettingSection>
          <SettingSection title="API Key">
            <input value={apiKey} onChange={e => setApiKey(e.target.value)} className="ink-input" type="password" placeholder={apiKey && apiKey.includes('••••') ? '已保存的 Key（输入新值覆盖）' : ''} />
          </SettingSection>
          <SettingSection title="API Base">
            <input value={apiBase} onChange={e => setApiBase(e.target.value)} className="ink-input" placeholder="https://api.openai.com/v1" />
          </SettingSection>
        </div>
      </div>

      <div className="mt-8 border-t border-tea pt-8">
        <h4 className="text-xs font-bold text-ink-lighter uppercase tracking-widest mb-4">检索参数</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <SettingSection title="Top-K（返回表数）">
            <input type="number" value={topK} onChange={e => setTopK(Math.max(1, Number(e.target.value)))} className="ink-input" min={1} max={20} />
            <p className="text-[10px] text-ink-lighter mt-1.5 font-kai">每次检索返回的最相关表数量</p>
          </SettingSection>
          <SettingSection title="最低相似度分数">
            <input type="number" value={minScore} onChange={e => setMinScore(Math.max(0, Math.min(1, Number(e.target.value))))} className="ink-input" min={0} max={1} step={0.05} />
            <p className="text-[10px] text-ink-lighter mt-1.5 font-kai">低于此分数的表会被过滤（0-1）</p>
          </SettingSection>
        </div>
      </div>
    </div>
  )
}
