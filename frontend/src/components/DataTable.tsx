import React from 'react'
import { useTranslation } from 'react-i18next'

export interface Column<T> {
  key: string
  header: string
  render?: (value: any, row: T, index: number) => React.ReactNode
  className?: string
  width?: string
}

interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  onRowClick?: (row: T) => void
  emptyMessage?: string
  loading?: boolean
  rowKey: (row: T) => string | number
}

export function DataTable<T>({ columns, data, onRowClick, emptyMessage, loading, rowKey }: DataTableProps<T>) {
  const { t } = useTranslation()
  if (loading) return null
  return (
    <div className="bg-white rounded-sm ink-border shadow-sm overflow-hidden w-full">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-smoke/50 text-left text-xs text-ink-lighter font-kai uppercase tracking-wider">
            {columns.map(col => (
              <th key={col.key} className={`px-6 py-4 font-bold ${col.className || ''}`} style={col.width ? { width: col.width } : undefined}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-tea/20">
          {data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-6 py-12 text-center text-ink-lighter font-kai text-sm italic">
                {emptyMessage || t('common.noData')}
              </td>
            </tr>
          ) : (
            data.map((row, i) => (
              <tr
                key={rowKey(row)}
                onClick={() => onRowClick?.(row)}
                className={`hover:bg-smoke/30 transition-colors ${onRowClick ? 'cursor-pointer' : ''}`}
              >
                {columns.map(col => (
                  <td key={col.key} className={`px-6 py-4 ${col.className || ''}`}>
                    {col.render ? col.render((row as any)[col.key], row, i) : (row as any)[col.key]}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
