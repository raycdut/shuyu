import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../../api'
import type { AdminStatsResponse } from '../../../types'

/** Format large numbers with K/M suffix for compact display. */
function formatNumber(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n.toLocaleString()
}

/** A single metric card displayed in the summary grid. */
function StatCard({ label, value, sub, icon, color }: { label: string; value: string; sub?: string; icon: string; color: string }) {
  return (
    <div className="bg-white rounded-sm ink-border shadow-sm p-6 flex items-start gap-4">
      <div className={`w-10 h-10 rounded-full flex items-center justify-center text-lg flex-shrink-0 ${color}`}>
        {icon}
      </div>
      <div className="min-w-0">
        <p className="text-xs text-ink-lighter font-kai mb-1">{label}</p>
        <p className="text-2xl font-song font-bold text-ink">{value}</p>
        {sub && <p className="text-xs text-ink-lighter font-kai mt-1">{sub}</p>}
      </div>
    </div>
  )
}

/** A compact bar chart for trend visualization without external dependencies. */
function MiniBarChart({ data, height = 80, color = 'bg-celadon' }: { data: { date: string; value: number }[]; height?: number; color?: string }) {
  const max = Math.max(...data.map(d => d.value), 1)
  return (
    <div className="flex items-end gap-1" style={{ height }}>
      {data.map((d, i) => (
        <div key={d.date} className="flex-1 flex flex-col items-center justify-end h-full gap-0.5">
          <div
            className={`w-full rounded-sm transition-all duration-300 ${color}`}
            style={{ height: `${(d.value / max) * 100}%`, minHeight: d.value > 0 ? '4px' : '1px', opacity: 0.7 + (i / data.length) * 0.3 }}
          />
        </div>
      ))}
    </div>
  )
}

/** Admin Dashboard tab showing system operation metrics and trends. */
export function DashboardTab() {
  const { t } = useTranslation()
  const [stats, setStats] = useState<AdminStatsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadStats = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getAdminStats(7)
      setStats(data)
    } catch (e: any) {
      setError(e.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadStats()
  }, [loadStats])

  if (loading) {
    return (
      <div className="w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
        <div className="flex items-center justify-between mb-8 border-b border-tea pb-4">
          <div>
            <h3 className="text-xl font-song font-bold text-ink">{t('adminDashboard.title')}</h3>
            <p className="text-xs text-ink-lighter font-kai mt-1">{t('adminDashboard.subtitle')}</p>
          </div>
        </div>
        <div className="py-12 text-center text-ink-lighter font-kai">{t('common.loading')}</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
        <div className="flex items-center justify-between mb-8 border-b border-tea pb-4">
          <div>
            <h3 className="text-xl font-song font-bold text-ink">{t('adminDashboard.title')}</h3>
            <p className="text-xs text-ink-lighter font-kai mt-1">{t('adminDashboard.subtitle')}</p>
          </div>
        </div>
        <div className="py-12 text-center">
          <p className="text-cinnabar font-kai mb-4">{error}</p>
          <button onClick={loadStats} className="px-4 py-2 bg-celadon text-white text-sm rounded-sm hover:bg-celadon-dark transition-colors font-kai">
            {t('common.refresh')}
          </button>
        </div>
      </div>
    )
  }

  if (!stats) return null

  const { overview, trends, top_users, model_usage } = stats

  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="flex items-center justify-between mb-8 border-b border-tea pb-4">
        <div>
          <h3 className="text-xl font-song font-bold text-ink">{t('adminDashboard.title')}</h3>
          <p className="text-xs text-ink-lighter font-kai mt-1">{t('adminDashboard.subtitle')}</p>
        </div>
        <button onClick={loadStats} className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-ink-light hover:text-celadon border border-tea/50 rounded-sm hover:border-celadon/30 transition-colors font-kai">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="23 4 23 10 17 10" /><polyline points="1 20 1 14 7 14" />
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
          </svg>
          {t('common.refresh')}
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label={t('adminDashboard.todayLogins')}
          value={formatNumber(overview.today_logins)}
          sub={t('adminDashboard.totalUsers') + ': ' + formatNumber(overview.total_users)}
          icon="👤"
          color="bg-blue-50 text-blue-600"
        />
        <StatCard
          label={t('adminDashboard.todayQuestions')}
          value={formatNumber(overview.today_questions)}
          sub={t('adminDashboard.totalSessions') + ': ' + formatNumber(overview.total_sessions)}
          icon="💬"
          color="bg-emerald-50 text-emerald-600"
        />
        <StatCard
          label={t('adminDashboard.todayTokens')}
          value={formatNumber(overview.today_token_total)}
          sub={`Prompt ${formatNumber(overview.today_token_prompt)} · Completion ${formatNumber(overview.today_token_completion)}`}
          icon="⚡"
          color="bg-amber-50 text-amber-600"
        />
        <StatCard
          label={t('adminDashboard.totalMessages')}
          value={formatNumber(overview.total_messages)}
          icon="📊"
          color="bg-purple-50 text-purple-600"
        />
      </div>

      {/* Trends */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-sm ink-border shadow-sm p-5">
          <h4 className="text-sm font-song font-bold text-ink mb-3">{t('adminDashboard.trendActiveUsers')}</h4>
          <MiniBarChart data={trends.active_users} color="bg-blue-400" />
          <div className="flex justify-between mt-2 text-[10px] text-ink-lighter font-kai">
            <span>{trends.active_users[0]?.date?.slice(5) || ''}</span>
            <span>{trends.active_users[trends.active_users.length - 1]?.date?.slice(5) || ''}</span>
          </div>
        </div>
        <div className="bg-white rounded-sm ink-border shadow-sm p-5">
          <h4 className="text-sm font-song font-bold text-ink mb-3">{t('adminDashboard.trendQuestions')}</h4>
          <MiniBarChart data={trends.questions} color="bg-emerald-400" />
          <div className="flex justify-between mt-2 text-[10px] text-ink-lighter font-kai">
            <span>{trends.questions[0]?.date?.slice(5) || ''}</span>
            <span>{trends.questions[trends.questions.length - 1]?.date?.slice(5) || ''}</span>
          </div>
        </div>
        <div className="bg-white rounded-sm ink-border shadow-sm p-5">
          <h4 className="text-sm font-song font-bold text-ink mb-3">{t('adminDashboard.trendTokenUsage')}</h4>
          <MiniBarChart data={trends.token_usage} color="bg-amber-400" />
          <div className="flex justify-between mt-2 text-[10px] text-ink-lighter font-kai">
            <span>{trends.token_usage[0]?.date?.slice(5) || ''}</span>
            <span>{trends.token_usage[trends.token_usage.length - 1]?.date?.slice(5) || ''}</span>
          </div>
        </div>
      </div>

      {/* Bottom section: Top Users & Model Usage */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Active Users */}
        <div className="bg-white rounded-sm ink-border shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-tea/30">
            <h4 className="text-sm font-song font-bold text-ink">{t('adminDashboard.topUsers')}</h4>
          </div>
          {top_users.length === 0 ? (
            <div className="px-5 py-8 text-center text-xs text-ink-lighter font-kai">{t('adminDashboard.noData')}</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-smoke/30 text-left text-[10px] text-ink-lighter font-kai uppercase tracking-wider">
                  <th className="px-5 py-3 font-bold">{t('adminDashboard.colRank')}</th>
                  <th className="px-5 py-3 font-bold">{t('adminDashboard.colUser')}</th>
                  <th className="px-5 py-3 font-bold text-right">{t('adminDashboard.colQuestions')}</th>
                  <th className="px-5 py-3 font-bold text-right">{t('adminDashboard.colLastActive')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-tea/20">
                {top_users.map((u, i) => (
                  <tr key={u.username} className="hover:bg-smoke/30 transition-colors">
                    <td className="px-5 py-3">
                      <span className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold ${
                        i === 0 ? 'bg-amber-100 text-amber-700' :
                        i === 1 ? 'bg-gray-100 text-gray-600' :
                        i === 2 ? 'bg-orange-100 text-orange-700' :
                        'text-ink-lighter'
                      }`}>
                        {i + 1}
                      </span>
                    </td>
                    <td className="px-5 py-3 font-medium text-ink">{u.username}</td>
                    <td className="px-5 py-3 text-right font-kai text-ink">{u.question_count}</td>
                    <td className="px-5 py-3 text-right text-xs text-ink-lighter font-kai">{u.last_active}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Model Usage */}
        <div className="bg-white rounded-sm ink-border shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-tea/30">
            <h4 className="text-sm font-song font-bold text-ink">{t('adminDashboard.modelUsage')}</h4>
          </div>
          {model_usage.length === 0 ? (
            <div className="px-5 py-8 text-center text-xs text-ink-lighter font-kai">{t('adminDashboard.noData')}</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-smoke/30 text-left text-[10px] text-ink-lighter font-kai uppercase tracking-wider">
                  <th className="px-5 py-3 font-bold">{t('adminDashboard.colModel')}</th>
                  <th className="px-5 py-3 font-bold text-right">{t('adminDashboard.colCalls')}</th>
                  <th className="px-5 py-3 font-bold text-right">{t('adminDashboard.colTokens')}</th>
                  <th className="px-5 py-3 font-bold text-right">{t('adminDashboard.colAvgTokens')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-tea/20">
                {model_usage.map((m, i) => (
                  <tr key={m.model + i} className="hover:bg-smoke/30 transition-colors">
                    <td className="px-5 py-3 font-medium text-ink">
                      <span className="font-mono text-xs">{m.model}</span>
                    </td>
                    <td className="px-5 py-3 text-right font-kai text-ink">{m.call_count}</td>
                    <td className="px-5 py-3 text-right font-kai text-ink">{formatNumber(m.total_tokens)}</td>
                    <td className="px-5 py-3 text-right text-xs text-ink-lighter font-kai">
                      {m.call_count > 0 ? formatNumber(Math.round(m.total_tokens / m.call_count)) : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
