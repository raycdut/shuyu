import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../../api'
import type { ConfigChangeLogEntry } from '../../../types'
import { PageHeader, LoadingState } from '../../../components/AdminSettings/Common'
import { DataTable } from '../../../components/DataTable'
import type { Column } from '../../../components/DataTable'

export function ConfigLogTab() {
  const { t } = useTranslation()
  const [logs, setLogs] = useState<ConfigChangeLogEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getConfigChangelog().then(setLogs).finally(() => setLoading(false))
  }, [])

  const columns: Column<ConfigChangeLogEntry>[] = [
    {
      key: 'created_at',
      header: t('configLog.colTime'),
      className: 'w-48',
      render: (v) => <span className="text-xs text-ink-lighter font-mono">{new Date(v).toLocaleString()}</span>,
    },
    {
      key: 'changed_by',
      header: t('configLog.colOperator'),
      className: 'w-32',
      render: (v) => <span className="text-xs font-semibold text-ink bg-tea/10 px-2 py-0.5 rounded-sm">{v}</span>,
    },
    {
      key: 'summary',
      header: t('configLog.colSummary'),
      render: (v) => <span className="text-sm text-ink leading-relaxed">{v}</span>,
    },
  ]

  if (loading) return <LoadingState />

  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
      <PageHeader title={t('configLog.title')} subtitle={t('configLog.subtitle')} />
      <DataTable columns={columns} data={logs} emptyMessage={t('configLog.noRecords')} rowKey={l => l.id} />
    </div>
  )
}
