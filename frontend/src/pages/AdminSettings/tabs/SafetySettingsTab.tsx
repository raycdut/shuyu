import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { SystemConfig } from '../../../types'
import { SettingSection, ToggleRow } from '../../../components/AdminSettings/Common'

export function SafetySettingsTab({ config, onSave, saving }: { config: SystemConfig; onSave: (p: Partial<SystemConfig>) => void; saving: boolean }) {
  const { t } = useTranslation()
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
          <h3 className="text-xl font-song font-bold text-ink">{t('safetySettings.title')}</h3>
          <p className="text-xs text-ink-lighter font-kai mt-1">{t('safetySettings.subtitle')}</p>
        </div>
        <button onClick={handleSave} disabled={saving} className="btn-celadon px-6 py-2 shadow-sm">{saving ? t('common.saving') : t('common.saveAllChanges')}</button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
        <div className="space-y-6">
          <h4 className="text-xs font-bold text-ink-lighter uppercase tracking-widest mb-4">{t('safetySettings.accessPolicy')}</h4>
          <div className="bg-white/40 p-4 rounded-sm border border-tea/30 space-y-2">
            <ToggleRow label={t('safetySettings.readonlyMode')} checked={readOnly} onChange={setReadOnly} />
            <ToggleRow label={t('safetySettings.requireConfirmation')} checked={requireApproval} onChange={setRequireApproval} />
            <ToggleRow label={t('safetySettings.allowUserOverride')} checked={allowOverride} onChange={setAllowOverride} />
          </div>
        </div>

        <div className="space-y-6">
          <h4 className="text-xs font-bold text-ink-lighter uppercase tracking-widest mb-4">{t('safetySettings.dataLimits')}</h4>
          <SettingSection title={t('safetySettings.maxRows')}>
            <input type="number" value={maxRows} onChange={e => setMaxRows(Number(e.target.value))} className="ink-input" min={10} max={10000} />
            <p className="text-[10px] text-ink-lighter mt-1.5 font-kai">{t('safetySettings.maxRowsHint')}</p>
          </SettingSection>
          <SettingSection title={t('safetySettings.blockedTables')}>
            <input value={blockedText} onChange={e => setBlockedText(e.target.value)} className="ink-input" placeholder="salary, pii_data, internal_audit" />
            <p className="text-[10px] text-ink-lighter mt-1.5 font-kai">{t('safetySettings.blockedTablesHint')}</p>
          </SettingSection>
        </div>
      </div>
    </div>
  )
}
