import { useState } from 'react'
import type { LLMConfig, SafetyConfig } from '../types'
import { api } from '../api'

interface ConfigPanelProps {
  open: boolean
  llmConfig: LLMConfig
  safetyConfig: SafetyConfig
  onLLMChange: (c: LLMConfig) => void
  onSafetyChange: (c: SafetyConfig) => void
  onConfigSave: () => void
}

const PROVIDERS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'azure', label: 'Azure OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'ollama', label: 'Ollama' },
  { value: 'custom', label: '自定义' },
]

const MODELS: Record<string, string[]> = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
  deepseek: ['deepseek-chat', 'deepseek-v4-flash', 'deepseek-v4-pro'],
  azure: ['gpt-4o', 'gpt-4', 'gpt-35-turbo'],
  anthropic: ['claude-3-5-sonnet', 'claude-3-haiku'],
  ollama: ['llama3.1', 'qwen2.5', 'mistral'],
  custom: ['custom'],
}

export default function ConfigPanel({
  open,
  llmConfig,
  safetyConfig,
  onLLMChange,
  onSafetyChange,
  onConfigSave,
}: ConfigPanelProps) {
  const [localLLM, setLocalLLM] = useState(llmConfig)
  const [localSafety, setLocalSafety] = useState(safetyConfig)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<string | null>(null)
  const [showKey, setShowKey] = useState(false)
  const [blockedText, setBlockedText] = useState('')
  const [temperature, setTemperature] = useState(0.3)

  if (!open) return null

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.updateConfig({ llm: localLLM, safety: localSafety })
      onLLMChange(localLLM)
      onSafetyChange(localSafety)
      onConfigSave()
    } catch { /* 静默 */ }
    setSaving(false)
  }

  const handleTestLLM = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await api.testLLM({
        api_key: localLLM.api_key,
        api_base: localLLM.api_base,
        model: localLLM.model,
      })
      setTestResult(res.ok ? '✅ 连接成功' : `❌ ${res.message}`)
    } catch (err: any) {
      setTestResult(`❌ ${err.message}`)
    }
    setTesting(false)
  }

  const currentModels = MODELS[localLLM.provider] || MODELS.openai

  return (
    <aside className="w-64 flex-shrink-0 bg-paper-light/50 overflow-y-auto">
      <div className="px-4 py-3">
        {/* ===== LLM 配置 ===== */}
        <Section title="LLM 提供商">
          <select
            value={localLLM.provider}
            onChange={e => {
              const p = e.target.value
              const defaults: Record<string, string> = {
                deepseek: 'https://api.deepseek.com',
                openai: 'https://api.openai.com/v1',
                ollama: 'http://localhost:11434/v1',
              }
              setLocalLLM({
                ...localLLM,
                provider: p,
                api_base: defaults[p] || localLLM.api_base,
                model: MODELS[p]?.[0] || localLLM.model,
              })
            }}
            className="ink-input text-sm"
          >
            {PROVIDERS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        </Section>

        <Section title="API Key">
          <div className="relative">
            <input
              type={showKey ? 'text' : 'password'}
              className="ink-input text-sm pr-8"
              value={localLLM.api_key}
              onChange={e => setLocalLLM({ ...localLLM, api_key: e.target.value })}
              placeholder="sk-..."
            />
            <button
              onClick={() => setShowKey(!showKey)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-lighter hover:text-ink"
            >
              {showKey ? (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </svg>
              ) : (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              )}
            </button>
          </div>
        </Section>

        <Section title="API Base">
          <input
            className="ink-input text-sm"
            value={localLLM.api_base}
            onChange={e => setLocalLLM({ ...localLLM, api_base: e.target.value })}
            placeholder="https://api.openai.com/v1"
          />
        </Section>

        <Section title="模型">
          <select
            value={localLLM.model}
            onChange={e => setLocalLLM({ ...localLLM, model: e.target.value })}
            className="ink-input text-sm"
          >
            {currentModels.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </Section>

        {/* 测试连接 */}
        <div className="flex gap-2 items-center mb-5">
          <button
            onClick={handleTestLLM}
            disabled={testing || !localLLM.api_key}
            className="px-3 py-1 text-xs text-ink-light hover:bg-smoke ink-border rounded-sm transition-colors disabled:opacity-40"
          >
            {testing ? '测试中…' : '🔌 测试'}
          </button>
          {testResult && (
            <span className="text-xs text-celadon-dark">{testResult}</span>
          )}
        </div>

        {/* ===== 分隔线 ===== */}
        <div className="ink-divider my-4" />

        {/* ===== 数据安全 ===== */}
        <h3 className="text-xs text-ink-lighter font-kai tracking-wider mb-3">数据安全</h3>

        <ToggleRow
          label="只读模式"
          desc="禁止修改数据的 SQL"
          checked={localSafety.read_only}
          onChange={v => setLocalSafety({ ...localSafety, read_only: v })}
        />

        <ToggleRow
          label="数据确认"
          desc="将数据发送到 LLM 前确认"
          checked={localSafety.require_approval}
          onChange={v => setLocalSafety({ ...localSafety, require_approval: v })}
        />

        <Section title="每页最多行数">
          <input
            type="number"
            className="ink-input text-sm"
            value={localSafety.max_rows}
            onChange={e => setLocalSafety({ ...localSafety, max_rows: Number(e.target.value) })}
            min={10}
            max={10000}
          />
        </Section>

        <Section title="屏蔽的表">
          <input
            className="ink-input text-sm"
            value={blockedText}
            onChange={e => setBlockedText(e.target.value)}
            placeholder="employee_salary, pii"
          />
        </Section>

        {/* ===== 分隔线 ===== */}
        <div className="ink-divider my-4" />

        {/* ===== 高级设置 ===== */}
        <h3 className="text-xs text-ink-lighter font-kai tracking-wider mb-3">高级设置</h3>

        <Section title="对话语言">
          <select className="ink-input text-sm" defaultValue="zh-CN">
            <option value="zh-CN">中文</option>
            <option value="en">English</option>
            <option value="ja">日本語</option>
          </select>
        </Section>

        <Section title={`温度: ${temperature.toFixed(1)}`}>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={temperature}
            onChange={e => setTemperature(Number(e.target.value))}
            className="w-full accent-celadon"
          />
          <div className="flex justify-between text-[10px] text-ink-lighter">
            <span>精确</span>
            <span>创造</span>
          </div>
        </Section>

        <Section title="会话过期">
          <div className="flex items-center gap-2">
            <input
              type="number"
              className="ink-input text-sm flex-1"
              defaultValue={60}
              min={5}
              max={1440}
            />
            <span className="text-xs text-ink-lighter">分钟</span>
          </div>
        </Section>

        {/* 保存按钮 */}
        <button
          onClick={handleSave}
          disabled={saving}
          className="btn-celadon w-full mt-4"
        >
          {saving ? '保存中…' : '保存配置'}
        </button>
      </div>
    </aside>
  )
}

// --- 子组件 ---

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <label className="block text-xs text-ink-lighter mb-1 font-kai">{title}</label>
      {children}
    </div>
  )
}

function ToggleRow({
  label,
  desc,
  checked,
  onChange,
}: {
  label: string
  desc: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <div className="flex items-start gap-3 mb-3">
      <button
        onClick={() => onChange(!checked)}
        className={`mt-0.5 w-4 h-4 flex-shrink-0 rounded-sm border transition-colors ${
          checked
            ? 'bg-celadon border-celadon text-white'
            : 'bg-white border-tea'
        }`}
      >
        {checked && (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        )}
      </button>
      <div>
        <div className="text-sm text-ink">{label}</div>
        <div className="text-xs text-ink-lighter font-kai">{desc}</div>
      </div>
    </div>
  )
}
