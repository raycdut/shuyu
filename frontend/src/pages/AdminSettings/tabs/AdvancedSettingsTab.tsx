import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { SettingSection, PageHeader } from '../../../components/AdminSettings/Common'
import { useAdminSettings } from '../AdminSettingsContext'

export function AdvancedSettingsTab() {
  const { t } = useTranslation()
  const { config, saving, save } = useAdminSettings()
  const [expire, setExpire] = useState(config.advanced.session_expire_minutes)
  const [maxSessions, setMaxSessions] = useState(config.advanced.max_sessions_per_user)

  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
      <PageHeader
        title={t('advancedSettings.title')}
        subtitle={t('advancedSettings.subtitle')}
        actions={
          <button onClick={() => save({ advanced: { session_expire_minutes: expire, max_sessions_per_user: maxSessions, allow_user_llm_config: config.advanced.allow_user_llm_config, allow_user_safety_override: config.advanced.allow_user_safety_override, llm_temperature_range: config.advanced.llm_temperature_range } })} disabled={saving} className="btn-celadon px-6 py-2 shadow-sm">
            {saving ? t('common.saving') : t('common.saveAllChanges')}
          </button>
        }
      />

      <div className="bg-white/40 p-6 rounded-sm border border-tea/30 max-w-lg">
        <h4 className="text-xs font-bold text-ink-lighter uppercase tracking-widest mb-4 border-l-2 border-celadon pl-3">{t('advancedSettings.sessionAndPerformance')}</h4>
        <SettingSection title={t('advancedSettings.sessionExpire')}>
          <input type="number" value={expire} onChange={e => setExpire(Number(e.target.value))} className="ink-input" min={5} max={43200} />
          <p className="text-[10px] text-ink-lighter mt-1 font-kai text-right">{t('advancedSettings.sessionExpireHint')}</p>
        </SettingSection>
        <SettingSection title={t('advancedSettings.maxParallelSessions')}>
          <input type="number" value={maxSessions} onChange={e => setMaxSessions(Number(e.target.value))} className="ink-input" min={1} max={500} />
        </SettingSection>
      </div>
    </div>
  )
}
