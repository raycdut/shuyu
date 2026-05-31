import { useState, useEffect } from 'react'
import { api } from '../../../api'
import type { ConfigChangeLogEntry } from '../../../types'

/**
 * 配置变更日志标签页
 */
export function ConfigLogTab() {
  const [logs, setLogs] = useState<ConfigChangeLogEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getConfigChangelog().then(setLogs).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="py-12 text-center text-ink-lighter font-kai">加载中…</div>

  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="flex items-center justify-between mb-8 border-b border-tea pb-4">
        <div>
          <h3 className="text-xl font-song font-bold text-ink">配置变更审计</h3>
          <p className="text-xs text-ink-lighter font-kai mt-1">追溯系统配置的每一次修改，确保配置变更可审计</p>
        </div>
      </div>

      <div className="bg-white rounded-sm ink-border shadow-sm overflow-hidden w-full">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-smoke/50 text-left text-xs text-ink-lighter font-kai uppercase tracking-wider">
              <th className="px-6 py-4 font-bold w-48">变更时间</th>
              <th className="px-6 py-4 font-bold w-32">操作人</th>
              <th className="px-6 py-4 font-bold">变更摘要</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-tea/20">
            {logs.map(log => (
              <tr key={log.id} className="hover:bg-smoke/10 transition-colors">
                <td className="px-6 py-4 text-xs text-ink-lighter font-mono">
                  {new Date(log.created_at).toLocaleString()}
                </td>
                <td className="px-6 py-4">
                  <span className="text-xs font-semibold text-ink bg-tea/10 px-2 py-0.5 rounded-sm">
                    {log.changed_by}
                  </span>
                </td>
                <td className="px-6 py-4 text-sm text-ink leading-relaxed">
                  {log.summary}
                </td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr>
                <td colSpan={3} className="px-6 py-12 text-center text-ink-lighter font-kai text-sm italic">
                  暂无任何配置变更记录
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
