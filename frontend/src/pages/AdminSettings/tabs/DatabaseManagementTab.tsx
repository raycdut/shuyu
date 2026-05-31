import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../../api'
import { useConfigStore } from '../../../store/configStore'
import type { DatabaseInfo, ImportedTable, SchemaStatus } from '../../../types'
import DescriptionEditor from '../../../components/DescriptionEditor'
import DBConnectModal from '../../../components/DBConnectModal'

type PageView = 'list' | 'detail'

const DB_ICONS: Record<string, string> = {
  duckdb: '🦆', postgres: '🐘', sqlite: '📄', mysql: '🐬', clickhouse: '🏠', snowflake: '❄️',
}

function SchemaDetailView({
  dbId,
  onBack,
}: {
  dbId: string
  onBack: () => void
}) {
  const { t } = useTranslation()
  const databases = useConfigStore(s => s.databases)
  const db = databases.find(d => d.id === dbId)
  const [schema, setSchema] = useState<ImportedTable[]>([])
  const [schemaStatus, setSchemaStatus] = useState<SchemaStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [importing, setImporting] = useState(false)
  const [describing, setDescribing] = useState(false)
  const [selectedTableId, setSelectedTableId] = useState<string | null>(null)
  const [tableSearch, setTableSearch] = useState('')
  const [showTableDropdown, setShowTableDropdown] = useState(false)

  const STATUS_BADGE: Record<string, { label: string; className: string }> = {
    pending: { label: t('dbSchema.statusNotImported'), className: 'bg-gray-100 text-gray-500' },
    importing: { label: t('dbSchema.statusImportingShort'), className: 'bg-blue-50 text-blue-600' },
    imported: { label: t('dbSchema.statusImportedShort'), className: 'bg-green-50 text-green-600' },
    error: { label: t('dbSchema.statusFailedShort'), className: 'bg-red-50 text-red-600' },
  }

  const loadSchema = useCallback(async () => {
    setLoading(true)
    try {
      const { tables } = await api.getImportedSchema(dbId)
      setSchema(tables)
    } catch {
      setSchema([])
    }
    setLoading(false)
  }, [dbId])

  const loadStatus = useCallback(async () => {
    try {
      const status = await api.getSchemaStatus(dbId)
      setSchemaStatus(status)
    } catch {
      setSchemaStatus(null)
    }
  }, [dbId])

  useEffect(() => {
    loadSchema()
    loadStatus()
  }, [loadSchema, loadStatus])

  // Auto-select first table on initial load only
  useEffect(() => {
    if (schema.length > 0 && !selectedTableId) {
      setSelectedTableId(schema[0].id)
    }
  }, [schema.length])

  const handleImport = async () => {
    setImporting(true)
    try {
      await api.importSchema(dbId)
      await loadSchema()
      await loadStatus()
    } catch {
      // ignore
    }
    setImporting(false)
  }

  const handleGenerateDescriptions = async () => {
    if (!selectedTableId) return
    setDescribing(true)
    try {
      await api.generateDescriptions(dbId, {
        table_ids: [selectedTableId],
        force: true,
      })
      await loadSchema()
      await loadStatus()
    } catch {
      // ignore
    }
    setDescribing(false)
  }

  const handleSaveDescription = async (tableId: string, columnId: string | null, description: string, descriptionEn?: string) => {
    await api.updateDescription(dbId, {
      table_id: columnId ? undefined : tableId,
      column_id: columnId || undefined,
      description,
      description_en: descriptionEn || '',
    })
  }

  const selectedTable = schema.find(t => t.id === selectedTableId)

  const filteredTables = tableSearch
    ? schema.filter(t => t.table_name.toLowerCase().includes(tableSearch.toLowerCase()))
    : schema

  const describedTables = schema.filter(t => t.description && t.description_en).length
  const describedColumns = schema.reduce((sum, t) =>
    sum + t.columns.filter(c => c.description && c.description_en).length, 0
  )
  const totalColumns = schema.reduce((sum, t) => sum + t.columns.length, 0)

  const isTableComplete = (t: ImportedTable) => {
    if (!t.description || !t.description_en) return false
    return t.columns.every(c => c.description && c.description_en)
  }

  return (
    <div>
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 mb-5 text-sm">
        <button onClick={onBack} className="text-gray-400 hover:text-gray-600 transition-colors">
          ← {t('dbSchema.backToList')}
        </button>
        {db && (
          <>
            <span className="text-gray-300">/</span>
            <span className="font-medium text-gray-700">{db.name}</span>
          </>
        )}
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <h3 className="text-base font-medium text-gray-800">
            {db && `${DB_ICONS[db.type] || '🗄'} ${db.name}`}
            {db && <span className="ml-2 text-sm font-normal text-gray-400">{db.type}</span>}
          </h3>
          {schemaStatus && schemaStatus.tables_count > 0 && (
            <span className={`ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_BADGE[schemaStatus.schema_status]?.className}`}>
              {STATUS_BADGE[schemaStatus.schema_status]?.label}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleImport}
            disabled={importing}
            className="h-8 px-3 text-xs font-medium text-gray-600 bg-white border border-gray-200 rounded-md hover:bg-gray-50 disabled:opacity-40 transition-colors"
          >
            {importing ? t('dbSchema.importing') : t('dbSchema.importSchema')}
          </button>
          <button
            onClick={handleGenerateDescriptions}
            disabled={describing || !schemaStatus || schemaStatus.tables_count === 0}
            className="h-8 px-3 text-xs font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-40 transition-colors"
          >
            {describing ? t('dbSchema.generating') : `AI ${t('dbSchema.generatingDesc')}`}
          </button>
          <button
            onClick={() => { loadSchema(); loadStatus() }}
            className="h-8 px-3 text-xs text-gray-500 bg-white border border-gray-200 rounded-md hover:bg-gray-50 transition-colors"
          >
            {t('dbSchema.refresh')}
          </button>
        </div>
      </div>

      {/* Stats bar */}
      {schemaStatus && schemaStatus.tables_count > 0 && (
        <div className="flex items-center gap-4 mb-4 px-3 py-2 bg-gray-50 rounded-md text-xs text-gray-500">
          <span>{t('dbSchema.table')} <strong className="text-gray-700">{schemaStatus.tables_count}</strong></span>
          <span>{t('dbSchema.field')} <strong className="text-gray-700">{schemaStatus.columns_count}</strong></span>
          <span>{t('dbSchema.described')} <strong className="text-green-600">{describedTables}</strong>{t('dbSchema.table')} / <strong className="text-green-600">{describedColumns}</strong>{t('dbSchema.field')}</span>
          <span>{t('dbSchema.completeness')} {totalColumns > 0 ? Math.round(describedColumns / totalColumns * 100) : 0}%</span>
        </div>
      )}

      {/* Loading / Empty */}
      {loading ? (
        <div className="h-64 flex items-center justify-center text-sm text-gray-400">{t('common.loading')}</div>
      ) : schema.length === 0 ? (
        <div className="h-64 flex flex-col items-center justify-center text-gray-400">
          <p className="text-sm mb-3">{t('dbSchema.notImportedYet')}</p>
          <button onClick={handleImport} disabled={importing} className="h-8 px-4 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700">
            {t('dbSchema.startImport')}
          </button>
        </div>
      ) : (
        <>
          {/* Table selector with filter */}
          <div className="mb-5">
            <label className="block text-xs text-gray-500 mb-1.5">{t('dbSchema.selectTable')}</label>
            <div className="relative">
              <input
                value={tableSearch}
                onChange={e => {
                  setTableSearch(e.target.value)
                  setShowTableDropdown(true)
                }}
                onFocus={() => setShowTableDropdown(true)}
                onBlur={() => setTimeout(() => setShowTableDropdown(false), 200)}
                placeholder={t('dbSchema.searchTable')}
                className="w-full h-10 pl-3 pr-10 text-sm bg-white border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
              <svg className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </div>

            {showTableDropdown && filteredTables.length > 0 && (
              <div className="mt-1 border border-gray-200 rounded-lg bg-white shadow-lg max-h-64 overflow-y-auto">
                {filteredTables.map(tbl => {
                  const complete = isTableComplete(tbl)
                  const described = tbl.columns.filter(c => c.description).length
                  const total = tbl.columns.length
                  const isSelected = tbl.id === selectedTableId
                  return (
                    <div
                      key={tbl.id}
                      onClick={() => {
                        setSelectedTableId(tbl.id)
                        setShowTableDropdown(false)
                        setTableSearch('')
                      }}
                      className={`flex items-center gap-2 px-3 py-2 cursor-pointer text-sm hover:bg-blue-50 transition-colors ${
                        isSelected ? 'bg-blue-50 font-medium' : ''
                      }`}
                    >
                      <span>{complete ? '🟢' : '🔴'}</span>
                      <span className="font-mono text-gray-800">{tbl.table_name}</span>
                      <span className="text-xs text-gray-400 ml-auto flex-shrink-0">
                        {t('dbSchema.fieldsDescribed', { count: described, total })}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Selected table detail */}
          {selectedTable && (
            <div className="bg-white border border-gray-200 rounded-lg">
              {/* Table header */}
              <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-mono font-medium text-gray-800">{selectedTable.table_name}</span>
                  {selectedTable.table_type === 'VIEW' && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-50 text-purple-600">VIEW</span>
                  )}
                  {selectedTable.columns.filter(c => c.description).length > 0 && (
                    <span className="text-xs text-green-600">
                      {t('dbSchema.fieldsDescribed', { count: selectedTable.columns.filter(c => c.description).length, total: selectedTable.columns.length })}
                    </span>
                  )}
                </div>
              </div>

              {/* Table descriptions */}
              <div className="px-4 py-3 border-b border-gray-50">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className="text-[10px] text-gray-400 font-mono">{t('dbSchema.descLangZh')}</span>
                      {selectedTable.description && <span className="text-green-500">✓</span>}
                    </div>
                    <DescriptionEditor
                      value={selectedTable.description}
                      onSave={async (desc) => {
                        await handleSaveDescription(selectedTable.id, null, desc, selectedTable.description_en)
                        setSchema(prev => prev.map(t => t.id === selectedTable.id ? { ...t, description: desc } : t))
                      }}
                      placeholder={t('dbSchema.addDescZh')}
                      className="text-sm text-gray-600"
                    />
                  </div>
                  <div>
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className="text-[10px] text-gray-400 font-mono">EN</span>
                      {selectedTable.description_en && <span className="text-green-500">✓</span>}
                    </div>
                    <DescriptionEditor
                      value={selectedTable.description_en}
                      onSave={async (descEn) => {
                        await handleSaveDescription(selectedTable.id, null, selectedTable.description, descEn)
                        setSchema(prev => prev.map(t => t.id === selectedTable.id ? { ...t, description_en: descEn } : t))
                      }}
                      placeholder={t('dbSchema.addDescEn')}
                      className="text-sm text-gray-600"
                    />
                  </div>
                </div>
              </div>

              {/* Columns */}
              <div className="divide-y divide-gray-50">
                {selectedTable.columns.length === 0 ? (
                  <div className="px-4 py-4 text-sm text-gray-400 text-center">{t('dbSchema.noFields')}</div>
                ) : (
                  selectedTable.columns.map(col => {
                    const cnDone = !!col.description
                    const enDone = !!col.description_en
                    const colComplete = cnDone && enDone
                    return (
                      <div key={col.id} className="px-4 py-3 hover:bg-gray-50/50">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`w-2 h-2 rounded-full ${colComplete ? 'bg-green-500' : 'bg-red-400'}`} />
                          <span className="text-sm font-mono text-gray-800">{col.column_name}</span>
                          <span className="text-xs text-gray-400 font-mono">{col.data_type}</span>
                          {col.is_primary_key && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-600 font-medium">PK</span>
                          )}
                        </div>
                        <div className="grid grid-cols-2 gap-4 pl-4">
                          <div className="flex items-start gap-1.5">
                            <span className="text-[10px] text-gray-300 font-mono mt-1.5 flex-shrink-0">{t('dbSchema.descLangZh')}</span>
                            <DescriptionEditor
                              value={col.description}
                              onSave={async (desc) => {
                                await handleSaveDescription(selectedTable.id, col.id, desc, col.description_en)
                                setSchema(prev => prev.map(t =>
                                  t.id === selectedTable.id ? { ...t, columns: t.columns.map(c => c.id === col.id ? { ...c, description: desc } : c) } : t
                                ))
                              }}
                              placeholder={t('dbSchema.addDescZh')}
                              className="text-sm text-gray-500"
                            />
                          </div>
                          <div className="flex items-start gap-1.5">
                            <span className="text-[10px] text-gray-300 font-mono mt-1.5 flex-shrink-0">EN</span>
                            <DescriptionEditor
                              value={col.description_en}
                              onSave={async (descEn) => {
                                await handleSaveDescription(selectedTable.id, col.id, col.description, descEn)
                                setSchema(prev => prev.map(t =>
                                  t.id === selectedTable.id ? { ...t, columns: t.columns.map(c => c.id === col.id ? { ...c, description_en: descEn } : c) } : t
                                ))
                              }}
                              placeholder={t('dbSchema.addDescEn')}
                              className="text-sm text-gray-500"
                            />
                          </div>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ===== Main Component =====

export function DatabaseManagementTab() {
  const { t } = useTranslation()
  const databases = useConfigStore(s => s.databases)
  const setDatabases = useConfigStore(s => s.setDatabases)
  const [view, setView] = useState<PageView>('list')
  const [detailDbId, setDetailDbId] = useState<string | null>(null)
  const [stats, setStats] = useState<Record<string, SchemaStatus>>({})
  const [loadingStats, setLoadingStats] = useState(false)
  const [showAddModal, setShowAddModal] = useState(false)
  const [editingDb, setEditingDb] = useState<DatabaseInfo | null>(null)

  const STATUS_BADGE: Record<string, { label: string; className: string }> = {
    pending: { label: t('dbSchema.statusNotImported'), className: 'bg-gray-100 text-gray-500' },
    importing: { label: t('dbSchema.statusImportingShort'), className: 'bg-blue-50 text-blue-600' },
    imported: { label: t('dbSchema.statusImportedShort'), className: 'bg-green-50 text-green-600' },
    error: { label: t('dbSchema.statusFailedShort'), className: 'bg-red-50 text-red-600' },
  }

  const loadDatabasesList = useCallback(async () => {
    try {
      const data = await api.getDatabases()
      setDatabases(data.databases || [])
    } catch {
      // ignore
    }
  }, [setDatabases])

  const loadAllStats = useCallback(async () => {
    if (databases.length === 0) return
    setLoadingStats(true)
    const results: Record<string, SchemaStatus> = {}
    await Promise.allSettled(
      databases.map(async (db) => {
        try {
          const status = await api.getSchemaStatus(db.id)
          results[db.id] = status
        } catch {
          results[db.id] = { schema_status: 'pending', tables_count: 0, columns_count: 0, described_tables: 0, described_columns: 0 }
        }
      })
    )
    setStats(results)
    setLoadingStats(false)
  }, [databases])

  useEffect(() => {
    loadDatabasesList()
  }, [loadDatabasesList])

  useEffect(() => {
    if (databases.length > 0) {
      loadAllStats()
    }
  }, [databases.length, loadAllStats])

  const handleDelete = async (dbId: string) => {
    if (!confirm(t('dbManager.confirmDeleteDb'))) return
    await api.disconnectDatabase(dbId)
    loadDatabasesList()
  }

  const handleViewDetail = (dbId: string) => {
    setDetailDbId(dbId)
    setView('detail')
  }

  if (view === 'detail' && detailDbId) {
    return <SchemaDetailView dbId={detailDbId} onBack={() => { setView('list'); setDetailDbId(null) }} />
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="text-base font-medium text-gray-800">{t('dbManager.title')}</h3>
          <p className="text-xs text-gray-400 mt-0.5">{t('dbManager.subtitle')}</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="h-8 px-4 text-xs font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors"
        >
          + {t('dbManager.addDatabaseBtn')}
        </button>
      </div>

      {/* Table */}
      {databases.length === 0 ? (
        <div className="h-64 flex flex-col items-center justify-center text-gray-400 border border-dashed border-gray-200 rounded-lg">
          <svg className="w-10 h-10 mb-2 text-gray-200" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <ellipse cx="12" cy="5" rx="9" ry="3" />
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
            <path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3" />
          </svg>
          <p className="text-sm mb-3">{t('dbManager.noDatabases')}</p>
          <button onClick={() => setShowAddModal(true)} className="h-8 px-4 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700">
            {t('dbManager.addDatabaseBtn')}
          </button>
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-500">{t('dbManager.columnDb')}</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-500">{t('dbManager.columnConnection')}</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-500">{t('dbManager.columnTableFilter')}</th>
                <th className="text-center px-4 py-2.5 text-xs font-medium text-gray-500">{t('dbManager.columnStatus')}</th>
                <th className="text-center px-4 py-2.5 text-xs font-medium text-gray-500">{t('dbManager.columnTableCount')}</th>
                <th className="text-center px-4 py-2.5 text-xs font-medium text-gray-500">{t('dbManager.columnSchemaDesc')}</th>
                <th className="text-right px-4 py-2.5 text-xs font-medium text-gray-500">{t('dbManager.columnActions')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {databases.map(db => {
                const s = stats[db.id]
                const tablesCount = s?.tables_count ?? 0
                const describedTables = s?.described_tables ?? 0
                const ratio = tablesCount > 0 ? Math.round(describedTables / tablesCount * 100) : 0

                return (
                  <tr key={db.id} className="hover:bg-gray-50/50 transition-colors">
                    {/* Name & Type */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="text-base">{DB_ICONS[db.type] || '🗄'}</span>
                        <div>
                          <div className="text-sm font-medium text-gray-800">{db.name}</div>
                          <div className="text-xs text-gray-400">{db.type}</div>
                        </div>
                      </div>
                    </td>

                    {/* Connection */}
                    <td className="px-4 py-3">
                      <div className="text-xs text-gray-500 font-mono max-w-[180px] truncate" title={db.path || db.connection_string || `${db.host || ''}:${db.port || ''}`}>
                        {db.path || db.connection_string || `${db.host || ''}:${db.port || ''}` || '-'}
                      </div>
                    </td>

                    {/* Table Filters */}
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {(db.include_tables || []).length > 0 && (
                          <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-green-50 text-green-600 border border-green-200">
                            <span>{t('dbManager.filterInclude')}</span>
                            <span className="font-mono">{db.include_tables!.join(', ')}</span>
                          </span>
                        )}
                        {(db.exclude_tables || []).length > 0 && (
                          <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-red-50 text-red-500 border border-red-200">
                            <span>{t('dbManager.filterExclude')}</span>
                            <span className="font-mono">{db.exclude_tables!.join(', ')}</span>
                          </span>
                        )}
                        {(!db.include_tables || db.include_tables.length === 0) &&
                         (!db.exclude_tables || db.exclude_tables.length === 0) && (
                          <span className="text-[10px] text-gray-300">{t('dbManager.allTables')}</span>
                        )}
                      </div>
                    </td>

                    {/* Status */}
                    <td className="px-4 py-3 text-center">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_BADGE[db.schema_status || 'pending']?.className}`}>
                        {STATUS_BADGE[db.schema_status || 'pending']?.label}
                      </span>
                    </td>

                    {/* Tables count */}
                    <td className="px-4 py-3 text-center text-sm text-gray-700">
                      {loadingStats ? '-' : tablesCount}
                    </td>

                    {/* Schema description ratio */}
                    <td className="px-4 py-3">
                      {loadingStats ? (
                        <div className="text-center text-xs text-gray-400">-</div>
                      ) : tablesCount > 0 ? (
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-blue-500 rounded-full transition-all"
                              style={{ width: `${ratio}%` }}
                            />
                          </div>
                          <span className="text-xs text-gray-500 w-14 text-right flex-shrink-0">
                            {describedTables}/{tablesCount}
                          </span>
                        </div>
                      ) : (
                        <div className="text-center text-xs text-gray-300">-</div>
                      )}
                    </td>

                    {/* Actions */}
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => setEditingDb(db)}
                          className="px-2 py-1 text-xs text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
                          title={t('dbManager.editConnection')}
                        >
                          {t('dbManager.edit')}
                        </button>
                        <button
                          onClick={() => handleViewDetail(db.id)}
                          className="px-2 py-1 text-xs text-blue-600 hover:bg-blue-50 rounded transition-colors"
                        >
                          {t('dbManager.manageSchema')}
                        </button>
                        <button
                          onClick={() => handleDelete(db.id)}
                          className="px-2 py-1 text-xs text-red-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                        >
                          {t('common.delete')}
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <DBConnectModal
        open={showAddModal}
        editDb={null}
        onClose={() => setShowAddModal(false)}
        onConnected={() => {
          setShowAddModal(false)
          loadDatabasesList()
        }}
      />

      {editingDb && (
        <DBConnectModal
          open={true}
          editDb={editingDb}
          onClose={() => setEditingDb(null)}
          onConnected={() => {
            setEditingDb(null)
            loadDatabasesList()
          }}
        />
      )}
    </div>
  )
}
