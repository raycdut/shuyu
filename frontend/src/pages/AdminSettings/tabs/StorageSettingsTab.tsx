import { useState } from 'react'
import type { SystemConfig } from '../../../types'
import { SettingSection } from '../../../components/AdminSettings/Common'

/**
 * 存储设置标签页
 */
export function StorageSettingsTab({ config, onSave, saving }: { config: SystemConfig; onSave: (p: Partial<SystemConfig>) => void; saving: boolean }) {
  const [logInterval, setLogInterval] = useState(config.storage.log_interval)
  const [retention, setRetention] = useState(config.storage.log_retention_days)

  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="flex items-center justify-between mb-8 border-b border-tea pb-4">
        <div>
          <h3 className="text-xl font-song font-bold text-ink">存储与日志设置</h3>
          <p className="text-xs text-ink-lighter font-kai mt-1">配置系统日志的记录频率与持久化策略</p>
        </div>
        <button onClick={() => onSave({ storage: { log_interval: logInterval, log_retention_days: retention } })} disabled={saving} className="btn-celadon px-6 py-2 shadow-sm">{saving ? '保存中…' : '保存所有更改'}</button>
      </div>

      <div className="max-w-2xl bg-white/40 p-8 rounded-sm border border-tea/30">
        <div className="space-y-8">
          <SettingSection title="日志归档周期">
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
                  {mode === 'hour' ? '每小时归档' : '每天归档'}
                </button>
              ))}
            </div>
          </SettingSection>

          <SettingSection title="历史记录保留天数">
            <div className="flex items-center gap-4">
              <input type="range" value={retention} onChange={e => setRetention(Number(e.target.value))} className="flex-1 accent-celadon" min={1} max={365} />
              <div className="w-20 text-center bg-white border border-tea py-2 rounded-sm text-sm font-semibold text-ink">
                {retention} 天
              </div>
            </div>
            <p className="text-[10px] text-ink-lighter mt-2 font-kai">超出此期限的日志将被系统自动清理以节省存储空间</p>
          </SettingSection>
        </div>
      </div>
    </div>
  )
}
