import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { SystemConfig } from '../../../types'
import { SettingSection } from '../../../components/AdminSettings/Common'

export function AdvancedSettingsTab({ config, onSave, saving }: { config: SystemConfig; onSave: (p: Partial<SystemConfig>) => void; saving: boolean }) {
  const { t } = useTranslation()
  const [expire, setExpire] = useState(config.advanced.session_expire_minutes)
  const [maxSessions, setMaxSessions] = useState(config.advanced.max_sessions_per_user)
  const [tempMin, setTempMin] = useState(config.advanced.llm_temperature_range.min)
  const [tempMax, setTempMax] = useState(config.advanced.llm_temperature_range.max)
  const [tempDefault, setTempDefault] = useState(config.advanced.llm_temperature_range.default)

  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="flex items-center justify-between mb-8 border-b border-tea pb-4">
        <div>
          <h3 className="text-xl font-song font-bold text-ink">{t('advancedSettings.title')}</h3>
          <p className="text-xs text-ink-lighter font-kai mt-1">{t('advancedSettings.subtitle')}</p>
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
          {saving ? t('common.saving') : t('common.saveAllChanges')}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
        <div className="space-y-8 bg-white/40 p-6 rounded-sm border border-tea/30">
          <h4 className="text-xs font-bold text-ink-lighter uppercase tracking-widest mb-4 border-l-2 border-celadon pl-3">{t('advancedSettings.sessionAndPerformance')}</h4>
          <SettingSection title={t('advancedSettings.sessionExpire')}>
            <input type="number" value={expire} onChange={e => setExpire(Number(e.target.value))} className="ink-input" min={5} max={43200} />
            <p className="text-[10px] text-ink-lighter mt-1 font-kai text-right">{t('advancedSettings.sessionExpireHint')}</p>
          </SettingSection>
          <SettingSection title={t('advancedSettings.maxParallelSessions')}>
            <input type="number" value={maxSessions} onChange={e => setMaxSessions(Number(e.target.value))} className="ink-input" min={1} max={500} />
          </SettingSection>
        </div>

        <div className="space-y-8 bg-white/40 p-6 rounded-sm border border-tea/30">
          <h4 className="text-xs font-bold text-ink-lighter uppercase tracking-widest mb-4 border-l-2 border-celadon pl-3">{t('advancedSettings.llmSampling')}</h4>
          <div className="grid grid-cols-2 gap-4">
            <SettingSection title={t('advancedSettings.temperatureMin')}>
              <input type="number" value={tempMin} onChange={e => setTempMin(Number(e.target.value))} className="ink-input" min={0} max={1} step={0.1} />
            </SettingSection>
            <SettingSection title={t('advancedSettings.temperatureMax')}>
              <input type="number" value={tempMax} onChange={e => setTempMax(Number(e.target.value))} className="ink-input" min={0} max={2} step={0.1} />
            </SettingSection>
          </div>
          <SettingSection title={t('advancedSettings.temperatureDefault')}>
            <div className="flex items-center gap-4">
              <input type="range" value={tempDefault} onChange={e => setTempDefault(Number(e.target.value))} className="flex-1 accent-celadon" min={tempMin} max={tempMax} step={0.05} />
              <span className="w-12 text-center text-sm font-bold text-celadon-dark">{tempDefault}</span>
            </div>
            <p className="text-[10px] text-ink-lighter mt-2 font-kai">{t('advancedSettings.temperatureHint')}</p>
          </SettingSection>
        </div>
      </div>
    </div>
  )
}
