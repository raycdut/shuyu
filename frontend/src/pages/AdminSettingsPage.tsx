import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import type { SystemConfig } from '../types'
import { LLMSettingsTab } from './AdminSettings/tabs/LLMSettingsTab'
import { SafetySettingsTab } from './AdminSettings/tabs/SafetySettingsTab'
import { StorageSettingsTab } from './AdminSettings/tabs/StorageSettingsTab'
import { UserManagementTab } from './AdminSettings/tabs/UserManagementTab'
import { AdvancedSettingsTab } from './AdminSettings/tabs/AdvancedSettingsTab'
import { ConfigLogTab } from './AdminSettings/tabs/ConfigLogTab'
import { DatabasePlaceholder } from './AdminSettings/tabs/DatabasePlaceholder'

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

  const loadConfig = useCallback(async () => {
    try {
      const data = await api.getSystemConfig()
      setConfig(data)
    } catch (e: any) {
      console.error('加载配置失败:', e)
    }
  }, [])

  useEffect(() => {
    loadConfig()
  }, [loadConfig])

  const handleSave = useCallback(async (patch: Partial<SystemConfig>) => {
    setSaving(true)
    try {
      const updated = await api.updateSystemConfig(patch)
      setConfig(updated)
    } catch (e: any) {
      alert('保存失败: ' + e.message)
    } finally {
      setSaving(false)
    }
  }, [])

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
