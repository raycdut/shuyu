import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../../api'
import { useConfigStore } from '../../../store/configStore'
import type { DatabaseInfo, ImportedTable, SchemaStatus } from '../../../types'
import { PageHeader, LoadingState, EmptyState } from '../../../components/AdminSettings/Common'
import DescriptionEditor from '../../../components/DescriptionEditor'
import DBConnectModal from '../../../components/DBConnectModal'

type PageView = 'list' | 'detail'

const DB_ICONS: Record<string, string> = {
  duckdb: '\u{1F986}', postgres: '\u{1F418}', sqlite: '\u{1F4C4}', mysql: '\u{1F42C}', clickhouse: '\u{1F3E0}', snowflake: '\u2744\uFE0F',
}

const STATUS_BADGE: Record<string, { labelKey: string; className: string }> = {
  pending: { labelKey: 'dbSchema.statusNotImported', className: 'bg-smoke text-ink-lighter' },
  importing: { labelKey: 'dbSchema.statusImportingShort', className: 'bg-celadon/10 text-celadon-dark' },
  imported: { labelKey: 'dbSchema.statusImportedShort', className: 'bg-celadon/10 text-celadon-dark' },
  error: { labelKey: 'dbSchema.statusFailedShort', className: 'bg-cinnabar/10 text-cinnabar' },
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
      <div className="flex items-center gap-2 mb-5 text-sm">
        <button onClick={onBack} className="text-ink-lighter hover:text-ink transition-colors font-kai">
          &larr; {t('dbSchema.backToList')}
        </button>
        {db && (
          <>
            <span className="text-tea/50">/</span>
            <span className="font-medium text-ink font-kai">{db.name}</span>
          </>
        )}
      </div>

      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <h3 className="text-base font-song font-bold text-ink">
            {db && `${DB_ICONS[db.type] || '\u{1F5C4}\uFE0F'} ${db.name}`}
            {db && <span className="ml-2 text-sm font-normal text-ink-lighter">{db.type}</span>}
          </h3>
          {schemaStatus && schemaStatus.tables_count > 0 && (
            <span className={`inline-flex items-center px-2 py-0.5 rounded-sm text-xs font-medium ${STATUS_BADGE[schemaStatus.schema_status]?.className}`}>
              {t(STATUS_BADGE[schemaStatus.schema_status]?.labelKey || '')}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleImport}
            disabled={importing}
            className="px-3 py-1.5 text-xs text-ink-light bg-white border border-tea/40 rounded-sm hover:bg-smoke/30 disabled:opacity-40 transition-colors font-kai"
          >
            {importing ? t('dbSchema.importing') : t('dbSchema.importSchema')}
          </button>
          <button
            onClick={handleGenerateDescriptions}
            disabled={describing || !schemaStatus || schemaStatus.tables_count === 0}
            className="btn-celadon px-3 py-1.5 text-xs disabled:opacity-40"
          >
            {describing ? t('dbSchema.generating') : `AI ${t('dbSchema.generatingDesc')}`}
          </button>
          <button
            onClick={() => { loadSchema(); loadStatus() }}
            className="px-3 py-1.5 text-xs text-ink-light bg-white border border-tea/40 rounded-sm hover:bg-smoke/30 transition-colors font-kai"
          >
            {t('dbSchema.refresh')}
          </button>
        </div>
      </div>

      {schemaStatus && schemaStatus.tables_count > 0 && (
        <div className="flex items-center gap-4 mb-4 px-3 py-2 bg-smoke/30 rounded-sm text-xs text-ink-lighter font-kai">
          <span>{t('dbSchema.table')} <strong className="text-ink">{schemaStatus.tables_count}</strong></span>
          <span>{t('dbSchema.field')} <strong className="text-ink">{schemaStatus.columns_count}</strong></span>
          <span>{t('dbSchema.described')} <strong className="text-celadon-dark">{describedTables}</strong>{t('dbSchema.table')} / <strong className="text-celadon-dark">{describedColumns}</strong>{t('dbSchema.field')}</span>
          <span>{t('dbSchema.completeness')} {totalColumns > 0 ? Math.round(describedColumns / totalColumns * 100) : 0}%</span>
        </div>
      )}

      {loading ? (
        <LoadingState />
      ) : schema.length === 0 ? (
        <EmptyState
          message={t('dbSchema.notImportedYet')}
          action={<button onClick={handleImport} disabled={importing} className="btn-celadon px-4 py-1.5 text-sm">{t('dbSchema.startImport')}</button>}
        />
      ) : (
        <>
          <div className="mb-5">
            <label className="block text-xs text-ink-lighter mb-1.5 font-kai">{t('dbSchema.selectTable')}</label>
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
                className="ink-input w-full h-10 pl-3 pr-10 text-sm"
              />
              <svg className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-lighter pointer-events-none" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </div>

            {showTableDropdown && filteredTables.length > 0 && (
              <div className="mt-1 border border-tea/30 rounded-sm bg-white shadow-lg max-h-64 overflow-y-auto">
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
                      className={`flex items-center gap-2 px-3 py-2 cursor-pointer text-sm hover:bg-celadon/5 transition-colors font-kai ${
                        isSelected ? 'bg-celadon/5 font-semibold' : ''
                      }`}
                    >
                      <span>{complete ? '\u{1F7E2}' : '\u{1F534}'}</span>
                      <span className="font-mono text-ink">{tbl.table_name}</span>
                      <span className="text-xs text-ink-lighter ml-auto flex-shrink-0">
                        {t('dbSchema.fieldsDescribed', { count: described, total })}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {selectedTable && (
            <div className="bg-white border border-tea/30 rounded-sm">
              <div className="px-4 py-3 border-b border-tea/10 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-mono font-medium text-ink">{selectedTable.table_name}</span>
                  {selectedTable.table_type === 'VIEW' && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded-sm bg-celadon/10 text-celadon-dark font-mono">VIEW</span>
                  )}
                  {selectedTable.columns.filter(c => c.description).length > 0 && (
                    <span className="text-xs text-celadon-dark font-kai">
                      {t('dbSchema.fieldsDescribed', { count: selectedTable.columns.filter(c => c.description).length, total: selectedTable.columns.length })}
                    </span>
                  )}
                </div>
              </div>

              <div className="px-4 py-3 border-b border-tea/5">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className="text-[10px] text-ink-lighter font-mono">{t('dbSchema.descLangZh')}</span>
                      {selectedTable.description && <span className="text-celadon">{'\u2713'}</span>}
                    </div>
                    <DescriptionEditor
                      value={selectedTable.description}
                      onSave={async (desc) => {
                        await handleSaveDescription(selectedTable.id, null, desc, selectedTable.description_en)
                        setSchema(prev => prev.map(t => t.id === selectedTable.id ? { ...t, description: desc } : t))
                      }}
                      placeholder={t('dbSchema.addDescZh')}
                      className="text-sm text-ink"
                    />
                  </div>
                  <div>
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className="text-[10px] text-ink-lighter font-mono">EN</span>
                      {selectedTable.description_en && <span className="text-celadon">{'\u2713'}</span>}
                    </div>
                    <DescriptionEditor
                      value={selectedTable.description_en}
                      onSave={async (descEn) => {
                        await handleSaveDescription(selectedTable.id, null, selectedTable.description, descEn)
                        setSchema(prev => prev.map(t => t.id === selectedTable.id ? { ...t, description_en: descEn } : t))
                      }}
                      placeholder={t('dbSchema.addDescEn')}
                      className="text-sm text-ink"
                    />
                  </div>
                </div>
              </div>

              <div className="divide-y divide-tea/5">
                {selectedTable.columns.length === 0 ? (
                  <div className="px-4 py-4 text-sm text-ink-lighter text-center font-kai">{t('dbSchema.noFields')}</div>
                ) : (
                  selectedTable.columns.map(col => {
                    const cnDone = !!col.description
                    const enDone = !!col.description_en
                    const colComplete = cnDone && enDone
                    return (
                      <div key={col.id} className="px-4 py-3 hover:bg-smoke/30">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`w-2 h-2 rounded-full ${colComplete ? 'bg-celadon' : 'bg-cinnabar/60'}`} />
                          <span className="text-sm font-mono text-ink">{col.column_name}</span>
                          <span className="text-xs text-ink-lighter font-mono">{col.data_type}</span>
                          {col.is_primary_key && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded-sm bg-amber/10 text-amber-dark font-medium font-mono">PK</span>
                          )}
                        </div>
                        <div className="grid grid-cols-2 gap-4 pl-4">
                          <div className="flex items-start gap-1.5">
                            <span className="text-[10px] text-tea/50 font-mono mt-1.5 flex-shrink-0">{t('dbSchema.descLangZh')}</span>
                            <DescriptionEditor
                              value={col.description}
                              onSave={async (desc) => {
                                await handleSaveDescription(selectedTable.id, col.id, desc, col.description_en)
                                setSchema(prev => prev.map(t =>
                                  t.id === selectedTable.id ? { ...t, columns: t.columns.map(c => c.id === col.id ? { ...c, description: desc } : c) } : t
                                ))
                              }}
                              placeholder={t('dbSchema.addDescZh')}
                              className="text-sm text-ink"
                            />
                          </div>
                          <div className="flex items-start gap-1.5">
                            <span className="text-[10px] text-tea/50 font-mono mt-1.5 flex-shrink-0">EN</span>
                            <DescriptionEditor
                              value={col.description_en}
                              onSave={async (descEn) => {
                                await handleSaveDescription(selectedTable.id, col.id, col.description, descEn)
                                setSchema(prev => prev.map(t =>
                                  t.id === selectedTable.id ? { ...t, columns: t.columns.map(c => c.id === col.id ? { ...c, description_en: descEn } : c) } : t
                                ))
                              }}
                              placeholder={t('dbSchema.addDescEn')}
                              className="text-sm text-ink"
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
    <div className="w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
      <PageHeader
        title={t('dbManager.title')}
        subtitle={t('dbManager.subtitle')}
        actions={
          <button onClick={() => setShowAddModal(true)} className="btn-celadon px-4 py-2 text-xs shadow-sm">
            + {t('dbManager.addDatabaseBtn')}
          </button>
        }
      />

      {databases.length === 0 ? (
        <EmptyState
          message={t('dbManager.noDatabases')}
          icon={
            <svg className="w-10 h-10 text-tea/50" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <ellipse cx="12" cy="5" rx="9" ry="3" />
              <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
              <path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3" />
            </svg>
          }
          action={<button onClick={() => setShowAddModal(true)} className="btn-celadon px-4 py-1.5 text-sm">{t('dbManager.addDatabaseBtn')}</button>}
        />
      ) : (
        <div className="bg-white rounded-sm ink-border shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-smoke/50 border-b border-tea/20">
                <th className="text-left px-4 py-2.5 text-xs font-bold text-ink-lighter font-kai uppercase tracking-wider">{t('dbManager.columnDb')}</th>
                <th className="text-left px-4 py-2.5 text-xs font-bold text-ink-lighter font-kai uppercase tracking-wider">{t('dbManager.columnConnection')}</th>
                <th className="text-left px-4 py-2.5 text-xs font-bold text-ink-lighter font-kai uppercase tracking-wider">{t('dbManager.columnTableFilter')}</th>
                <th className="text-center px-4 py-2.5 text-xs font-bold text-ink-lighter font-kai uppercase tracking-wider">{t('dbManager.columnStatus')}</th>
                <th className="text-center px-4 py-2.5 text-xs font-bold text-ink-lighter font-kai uppercase tracking-wider">{t('dbManager.columnTableCount')}</th>
                <th className="text-center px-4 py-2.5 text-xs font-bold text-ink-lighter font-kai uppercase tracking-wider">{t('dbManager.columnSchemaDesc')}</th>
                <th className="text-right px-4 py-2.5 text-xs font-bold text-ink-lighter font-kai uppercase tracking-wider">{t('dbManager.columnActions')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-tea/20">
              {databases.map(db => {
                const s = stats[db.id]
                const tablesCount = s?.tables_count ?? 0
                const describedTables = s?.described_tables ?? 0
                const ratio = tablesCount > 0 ? Math.round(describedTables / tablesCount * 100) : 0

                return (
                  <tr key={db.id} className="hover:bg-smoke/30 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="text-base">{DB_ICONS[db.type] || '\u{1F5C4}\uFE0F'}</span>
                        <div>
                          <div className="text-sm font-medium text-ink">{db.name}</div>
                          <div className="text-xs text-ink-lighter">{db.type}</div>
                        </div>
                      </div>
                    </td>

                    <td className="px-4 py-3">
                      <div className="text-xs text-ink-lighter font-mono max-w-[180px] truncate" title={db.path || db.connection_string || `${db.host || ''}:${db.port || ''}`}>
                        {db.path || db.connection_string || `${db.host || ''}:${db.port || ''}` || '-'}
                      </div>
                    </td>

                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {(db.include_tables || []).length > 0 && (
                          <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-sm bg-celadon/10 text-celadon-dark border border-celadon/20">
                            <span>{t('dbManager.filterInclude')}</span>
                            <span className="font-mono">{db.include_tables!.join(', ')}</span>
                          </span>
                        )}
                        {(db.exclude_tables || []).length > 0 && (
                          <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-sm bg-cinnabar/10 text-cinnabar border border-cinnabar/20">
                            <span>{t('dbManager.filterExclude')}</span>
                            <span className="font-mono">{db.exclude_tables!.join(', ')}</span>
                          </span>
                        )}
                        {(!db.include_tables || db.include_tables.length === 0) &&
                         (!db.exclude_tables || db.exclude_tables.length === 0) && (
                          <span className="text-[10px] text-tea/50">{t('dbManager.allTables')}</span>
                        )}
                      </div>
                    </td>

                    <td className="px-4 py-3 text-center">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-sm text-xs font-medium ${STATUS_BADGE[db.schema_status || 'pending']?.className}`}>
                        {t(STATUS_BADGE[db.schema_status || 'pending']?.labelKey || '')}
                      </span>
                    </td>

                    <td className="px-4 py-3 text-center text-sm text-ink font-kai">
                      {loadingStats ? '-' : tablesCount}
                    </td>

                    <td className="px-4 py-3">
                      {loadingStats ? (
                        <div className="text-center text-xs text-ink-lighter">-</div>
                      ) : tablesCount > 0 ? (
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1.5 bg-smoke rounded-full overflow-hidden">
                            <div
                              className="h-full bg-celadon rounded-full transition-all"
                              style={{ width: `${ratio}%` }}
                            />
                          </div>
                          <span className="text-xs text-ink-lighter w-14 text-right flex-shrink-0 font-kai">
                            {describedTables}/{tablesCount}
                          </span>
                        </div>
                      ) : (
                        <div className="text-center text-xs text-tea/50">-</div>
                      )}
                    </td>

                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => setEditingDb(db)}
                          className="px-2 py-1 text-xs text-ink-lighter hover:text-ink hover:bg-smoke/50 rounded-sm transition-colors font-kai"
                          title={t('dbManager.editConnection')}
                        >
                          {t('dbManager.edit')}
                        </button>
                        <button
                          onClick={() => handleViewDetail(db.id)}
                          className="px-2 py-1 text-xs text-celadon-dark hover:bg-celadon/5 rounded-sm transition-colors font-kai"
                        >
                          {t('dbManager.manageSchema')}
                        </button>
                        <button
                          onClick={() => handleDelete(db.id)}
                          className="px-2 py-1 text-xs text-cinnabar hover:text-cinnabar hover:bg-cinnabar/5 rounded-sm transition-colors font-kai"
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
