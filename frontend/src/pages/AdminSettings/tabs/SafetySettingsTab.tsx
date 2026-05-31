import { useState } from 'react'
import type { SystemConfig } from '../../../types'
import { SettingSection, ToggleRow } from '../../../components/AdminSettings/Common'

/**
 * 安全设置标签页
 */
export function SafetySettingsTab({ config, onSave, saving }: { config: SystemConfig; onSave: (p: Partial<SystemConfig>) => void; saving: boolean }) {
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
