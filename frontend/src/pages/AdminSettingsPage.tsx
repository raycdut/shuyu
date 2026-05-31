import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import type { SystemConfig } from '../types'
import { DashboardTab } from './AdminSettings/tabs/DashboardTab'
import { LLMSettingsTab } from './AdminSettings/tabs/LLMSettingsTab'
import { SafetySettingsTab } from './AdminSettings/tabs/SafetySettingsTab'
import { StorageSettingsTab } from './AdminSettings/tabs/StorageSettingsTab'
import { UserManagementTab } from './AdminSettings/tabs/UserManagementTab'
import { AdvancedSettingsTab } from './AdminSettings/tabs/AdvancedSettingsTab'
import { ConfigLogTab } from './AdminSettings/tabs/ConfigLogTab'
import { DatabaseManagementTab } from './AdminSettings/tabs/DatabaseManagementTab'
import { PromptManagementTab } from './AdminSettings/tabs/PromptManagementTab'

type AdminTab = 'dashboard' | 'llm' | 'safety' | 'storage' | 'database' | 'users' | 'advanced' | 'logs' | 'prompts'

interface TabGroup {
  groupKey: string
  label: string
  items: { key: AdminTab; label: string }[]
}

export default function AdminSettingsPage() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState<AdminTab>('dashboard')
  const [config, setConfig] = useState<SystemConfig | null>(null)
  const [saving, setSaving] = useState(false)
  const navigate = useNavigate()

  const TAB_GROUPS: TabGroup[] = [
    {
      groupKey: 'overview',
      label: t('adminSettings.groupOverview'),
      items: [{ key: 'dashboard', label: t('adminSettings.dashboard') }],
    },
    {
      groupKey: 'system',
      label: t('adminSettings.groupSystem'),
      items: [
        { key: 'llm', label: t('adminSettings.llmProvider') },
        { key: 'safety', label: t('adminSettings.safety') },
        { key: 'storage', label: t('adminSettings.storage') },
        { key: 'advanced', label: t('adminSettings.advanced') },
      ],
    },
    {
      groupKey: 'resources',
      label: t('adminSettings.groupResources'),
      items: [
        { key: 'database', label: t('adminSettings.dbManagement') },
        { key: 'users', label: t('adminSettings.userManagement') },
      ],
    },
    {
      groupKey: 'ops',
      label: t('adminSettings.groupOps'),
      items: [
        { key: 'prompts', label: 'Prompt 管理' },
        { key: 'logs', label: t('adminSettings.configLog') },
      ],
    },
  ]

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
      alert(`${t('saveFailed')}: ${e.message}`)
    } finally {
      setSaving(false)
    }
  }, [t])

  if (!config) {
    return <div className="min-h-screen flex items-center justify-center bg-paper-light"><p className="text-ink-lighter font-kai">{t('app.loading')}</p></div>
  }

  return (
    <div className="flex-1 flex bg-paper-light overflow-hidden w-full">
      <nav className="w-56 flex-shrink-0 bg-white/60 border-r border-tea py-6 shadow-sm z-10">
        <div className="px-6 mb-6">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2 text-sm text-ink-light hover:text-celadon transition-colors font-sans mb-4"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" />
            </svg>
            {t('nav.backToChat')}
          </button>
          <h2 className="text-xs font-song font-bold text-ink-lighter uppercase tracking-widest">{t('nav.systemAdmin')}</h2>
        </div>
        <div className="space-y-6">
          {TAB_GROUPS.map(group => (
            <div key={group.groupKey}>
              <h3 className="px-6 mb-1.5 text-[10px] font-song font-bold text-ink-lighter uppercase tracking-widest">
                {group.label}
              </h3>
              <div className="space-y-0.5">
                {group.items.map(tab => (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`w-full text-left px-6 py-2.5 text-sm transition-all duration-200 font-kai flex items-center gap-3 ${
                      activeTab === tab.key
                        ? 'bg-celadon text-white shadow-md'
                        : 'text-ink-light hover:bg-smoke hover:pl-7'
                    }`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${activeTab === tab.key ? 'bg-white' : 'bg-tea/40'}`} />
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </nav>

      <main className="flex-1 overflow-y-auto bg-paper-light/30">
        <div className="w-full h-full min-w-[600px] p-8 lg:p-12">
          <div className="max-w-6xl mx-auto">
            {activeTab === 'dashboard' && <DashboardTab />}
            {activeTab === 'llm' && <LLMSettingsTab config={config} onSave={handleSave} saving={saving} />}
            {activeTab === 'safety' && <SafetySettingsTab config={config} onSave={handleSave} saving={saving} />}
            {activeTab === 'storage' && <StorageSettingsTab config={config} onSave={handleSave} saving={saving} />}
            {activeTab === 'database' && <DatabaseManagementTab />}
            {activeTab === 'users' && <UserManagementTab />}
            {activeTab === 'prompts' && <PromptManagementTab />}
            {activeTab === 'advanced' && <AdvancedSettingsTab config={config} onSave={handleSave} saving={saving} />}
            {activeTab === 'logs' && <ConfigLogTab />}
          </div>
        </div>
      </main>
    </div>
  )
}
