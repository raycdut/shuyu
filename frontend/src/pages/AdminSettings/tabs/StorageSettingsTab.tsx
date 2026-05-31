import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { SystemConfig } from '../../../types'
import { SettingSection } from '../../../components/AdminSettings/Common'

export function StorageSettingsTab({ config, onSave, saving }: { config: SystemConfig; onSave: (p: Partial<SystemConfig>) => void; saving: boolean }) {
  const { t } = useTranslation()
  const [logInterval, setLogInterval] = useState(config.storage.log_interval)
  const [retention, setRetention] = useState(config.storage.log_retention_days)

  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="flex items-center justify-between mb-8 border-b border-tea pb-4">
        <div>
          <h3 className="text-xl font-song font-bold text-ink">{t('storageSettings.title')}</h3>
          <p className="text-xs text-ink-lighter font-kai mt-1">{t('storageSettings.subtitle')}</p>
        </div>
        <button onClick={() => onSave({ storage: { log_interval: logInterval, log_retention_days: retention } })} disabled={saving} className="btn-celadon px-6 py-2 shadow-sm">{saving ? t('common.saving') : t('common.saveAllChanges')}</button>
      </div>

      <div className="max-w-2xl bg-white/40 p-8 rounded-sm border border-tea/30">
        <div className="space-y-8">
          <SettingSection title={t('storageSettings.logArchivePeriod')}>
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
                  {mode === 'hour' ? t('storageSettings.archiveHourly') : t('storageSettings.archiveDaily')}
                </button>
              ))}
            </div>
          </SettingSection>

          <SettingSection title={t('storageSettings.retentionDays')}>
            <div className="flex items-center gap-4">
              <input type="range" value={retention} onChange={e => setRetention(Number(e.target.value))} className="flex-1 accent-celadon" min={1} max={365} />
              <div className="w-20 text-center bg-white border border-tea py-2 rounded-sm text-sm font-semibold text-ink">
                {retention} {t('storageSettings.days')}
              </div>
            </div>
            <p className="text-[10px] text-ink-lighter mt-2 font-kai">{t('storageSettings.retentionHint')}</p>
          </SettingSection>
        </div>
      </div>
    </div>
  )
}
