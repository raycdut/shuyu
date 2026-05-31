import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useConfigStore } from '../store/configStore'
import type { ImportedTable, SchemaStatus } from '../types'
import DescriptionEditor from '../components/DescriptionEditor'
import DBConnectModal from '../components/DBConnectModal'


const DB_ICONS: Record<string, string> = {
  duckdb: '🦆', postgres: '🐘', sqlite: '📄', mysql: '🐬', clickhouse: '🏠', snowflake: '❄️',
}

export default function DatabaseManagerPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const databases = useConfigStore(s => s.databases)
  const setDatabases = useConfigStore(s => s.setDatabases)
  const [selectedDbId, setSelectedDbId] = useState<string | null>(null)
  const [schema, setSchema] = useState<ImportedTable[]>([])
  const [schemaStatus, setSchemaStatus] = useState<SchemaStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [importing, setImporting] = useState(false)
  const [describing, setDescribing] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [searchText, setSearchText] = useState('')
  const [filterDescribed, setFilterDescribed] = useState<'all' | 'described' | 'undescribed'>('all')
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set())
  const [showAddModal, setShowAddModal] = useState(false)

  const selectedDb = databases.find(d => d.id === selectedDbId)

  const STATUS_LABELS: Record<string, { label: string; className: string }> = {
    pending: { label: t('dbSchema.statusPending'), className: 'bg-tea/20 text-tea-dark' },
    importing: { label: t('dbSchema.statusImporting'), className: 'bg-amber/10 text-amber' },
    imported: { label: t('dbSchema.statusImported'), className: 'bg-celadon/10 text-celadon-dark' },
    error: { label: t('dbSchema.statusFailed'), className: 'bg-cinnabar/5 text-cinnabar' },
  }

  useEffect(() => {
    if (databases.length > 0 && !selectedDbId) {
      setSelectedDbId(databases[0].id)
    }
  }, [databases, selectedDbId])

  useEffect(() => {
    if (selectedDbId) {
      loadSchema()
      loadStatus()
    }
  }, [selectedDbId])

  const loadDatabasesList = async () => {
    try {
      const data = await api.getDatabases()
      setDatabases(data.databases || [])
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    loadDatabasesList()
  }, [])

  const loadSchema = async () => {
    if (!selectedDbId) return
    setLoading(true)
    try {
      const { tables } = await api.getImportedSchema(selectedDbId)
      setSchema(tables)
      setExpandedTables(new Set(tables.map(t => t.id)))
    } catch {
      setSchema([])
    }
    setLoading(false)
  }

  const loadStatus = async () => {
    if (!selectedDbId) return
    try {
      const status = await api.getSchemaStatus(selectedDbId)
      setSchemaStatus(status)
    } catch {
      setSchemaStatus(null)
    }
  }

  const showMessage = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text })
    setTimeout(() => setMessage(null), 3000)
  }

  const handleImport = async () => {
    if (!selectedDbId) return
    setImporting(true)
    try {
      const res = await api.importSchema(selectedDbId)
      showMessage('success', res.message)
      await loadSchema()
      await loadStatus()
    } catch (err: any) {
      showMessage('error', err.message)
    }
    setImporting(false)
  }

  const handleGenerateDescriptions = async () => {
    if (!selectedDbId) return
    setDescribing(true)
    try {
      const res = await api.generateDescriptions(selectedDbId)
      showMessage('success', res.message)
      await loadSchema()
      await loadStatus()
    } catch (err: any) {
      showMessage('error', err.message)
    }
    setDescribing(false)
  }

  const handleSaveDescription = async (tableId: string, columnId: string | null, description: string) => {
    if (!selectedDbId) return
    await api.updateDescription(selectedDbId, {
      table_id: columnId ? undefined : tableId,
      column_id: columnId || undefined,
      description,
    })
  }

  const toggleTable = (tableId: string) => {
    setExpandedTables(prev => {
      const next = new Set(prev)
      if (next.has(tableId)) next.delete(tableId)
      else next.add(tableId)
      return next
    })
  }

  const filteredSchema = schema.filter(t => {
    const matchesSearch = !searchText || t.table_name.toLowerCase().includes(searchText.toLowerCase()) || t.description.toLowerCase().includes(searchText.toLowerCase())
    if (!matchesSearch) return false
    if (filterDescribed === 'described') return !!t.description
    if (filterDescribed === 'undescribed') return !t.description
    return true
  })

  return (
    <div className="h-full flex flex-col bg-paper">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 ink-border">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/')}
            className="p-1 rounded-sm text-ink-lighter hover:text-ink hover:bg-smoke transition-colors"
            title={t('common.back')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" />
            </svg>
          </button>
          <h1 className="text-base font-song font-semibold text-ink">{t('dbManager.title')}</h1>
        </div>
        {message && (
          <div className={`px-3 py-1.5 text-xs rounded-sm ${
            message.type === 'success' ? 'bg-celadon/10 text-celadon-dark' : 'bg-cinnabar/5 text-cinnabar'
          }`}>
            {message.text}
          </div>
        )}
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left: Database List */}
        <div className="w-56 flex-shrink-0 ink-border overflow-y-auto">
          <div className="px-3 py-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-ink-lighter font-kai tracking-wider">{t('dbManager.subtitle')}</span>
              <button
                onClick={() => setShowAddModal(true)}
                className="p-1 rounded-sm text-ink-lighter hover:text-celadon hover:bg-smoke transition-colors"
                title={t('dbManager.addDatabase')}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
                </svg>
              </button>
            </div>
            {databases.length === 0 ? (
              <div className="py-6 text-center text-xs text-ink-lighter font-kai">{t('dbManager.noDatabases')}</div>
            ) : (
              databases.map(db => (
                <button
                  key={db.id}
                  onClick={() => setSelectedDbId(db.id)}
                  className={`w-full text-left px-2.5 py-2 text-sm rounded-sm flex items-center gap-2 transition-colors ${
                    selectedDbId === db.id ? 'bg-celadon/10 text-celadon-dark font-medium' : 'text-ink-light hover:bg-smoke'
                  }`}
                >
                  <span className="text-xs">{DB_ICONS[db.type] || '🗄'}</span>
                  <span className="truncate flex-1">{db.name}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-sm ${STATUS_LABELS[db.schema_status || 'pending']?.className || ''}`}>
                    {STATUS_LABELS[db.schema_status || 'pending']?.label || t('dbSchema.statusPending')}
                  </span>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Right: Schema Content */}
        <div className="flex-1 overflow-y-auto">
          {!selectedDb ? (
            <div className="h-full flex items-center justify-center text-sm text-ink-lighter font-kai">
              {t('dbSchema.selectDb')}
            </div>
          ) : (
            <div className="max-w-4xl mx-auto px-6 py-5">
              {/* DB Info + Actions */}
              <div className="mb-6">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-lg">{DB_ICONS[selectedDb.type] || '🗄'}</span>
                  <h2 className="text-base font-song font-semibold text-ink">{selectedDb.name}</h2>
                  <span className="text-xs text-ink-lighter font-kai">{selectedDb.type}</span>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  <button
                    onClick={handleImport}
                    disabled={importing}
                    className="px-3 py-1.5 text-xs text-ink-light hover:bg-smoke ink-border rounded-sm transition-colors disabled:opacity-40"
                  >
                    {importing ? t('dbSchema.importing') : `📥 ${t('dbSchema.importSchema')}`}
                  </button>
                  <button
                    onClick={handleGenerateDescriptions}
                    disabled={describing || !schemaStatus || schemaStatus.tables_count === 0}
                    className="px-3 py-1.5 text-xs text-ink-light hover:bg-smoke ink-border rounded-sm transition-colors disabled:opacity-40"
                  >
                    {describing ? t('dbSchema.generating') : `🤖 ${t('dbSchema.generatingDesc')}`}
                  </button>
                  <button
                    onClick={() => { loadSchema(); loadStatus() }}
                    className="px-3 py-1.5 text-xs text-ink-lighter hover:bg-smoke rounded-sm transition-colors"
                  >
                    🔄 {t('dbSchema.refresh')}
                  </button>
                </div>

                {/* Schema Status Summary */}
                {schemaStatus && schemaStatus.tables_count > 0 && (
                  <div className="mt-3 flex items-center gap-4 text-xs text-ink-lighter font-kai">
                    <span>{t('dbSchema.table')}: <strong className="text-ink">{schemaStatus.tables_count}</strong></span>
                    <span>{t('dbSchema.field')}: <strong className="text-ink">{schemaStatus.columns_count}</strong></span>
                    <span>{t('dbSchema.describedTables')}: <strong className="text-celadon-dark">{schemaStatus.described_tables}</strong> / {schemaStatus.tables_count}</span>
                    <span>{t('dbSchema.describedFields')}: <strong className="text-celadon-dark">{schemaStatus.described_columns}</strong> / {schemaStatus.columns_count}</span>
                  </div>
                )}
              </div>

              {/* Filter Bar */}
              {(schema.length > 0 || loading) && (
                <div className="flex items-center gap-3 mb-4">
                  <input
                    className="ink-input text-xs flex-1 max-w-xs"
                    placeholder={t('dbSchema.searchTable')}
                    value={searchText}
                    onChange={e => setSearchText(e.target.value)}
                  />
                  <select
                    value={filterDescribed}
                    onChange={e => setFilterDescribed(e.target.value as any)}
                    className="ink-input text-xs w-28"
                  >
                    <option value="all">{t('dbSchema.filterAll')}</option>
                    <option value="undescribed">{t('dbSchema.filterUndescribed')}</option>
                    <option value="described">{t('dbSchema.filterDescribed')}</option>
                  </select>
                </div>
              )}

              {/* Loading / Content */}
              {loading ? (
                <div className="py-10 text-center text-sm text-ink-lighter font-kai">{t('common.loading')}</div>
              ) : filteredSchema.length === 0 ? (
                <div className="py-10 text-center">
                  {schema.length === 0 ? (
                    <div>
                      <p className="text-sm text-ink-lighter font-kai mb-3">{t('dbSchema.notImportedYet')}</p>
                      <button
                        onClick={handleImport}
                        disabled={importing}
                        className="px-4 py-2 text-sm text-white bg-celadon hover:bg-celadon-dark rounded-sm transition-colors"
                      >
                        {importing ? t('dbSchema.importing') : t('dbSchema.startImport')}
                      </button>
                    </div>
                  ) : (
                    <p className="text-sm text-ink-lighter font-kai">{t('dbSchema.noMatch')}</p>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  {filteredSchema.map(table => (
                    <div key={table.id} className="bg-paper-light paper-shadow-sm rounded-sm ink-border">
                      {/* Table Header */}
                      <button
                        onClick={() => toggleTable(table.id)}
                        className="w-full text-left px-4 py-2.5 flex items-center gap-2 hover:bg-smoke/50 transition-colors"
                      >
                        <span className={`text-[10px] w-3 text-center text-ink-lighter transition-transform ${expandedTables.has(table.id) ? 'rotate-90' : ''}`}>
                          ▶
                        </span>
                        <span className="text-xs">{table.table_type === 'VIEW' ? '👁' : '📋'}</span>
                        <span className="text-sm font-medium text-ink">{table.table_name}</span>
                        {table.description && (
                          <span className="text-xs text-celadon-dark">✓</span>
                        )}
                      </button>

                      {/* Table Description */}
                      <div className="px-4 pb-2">
                        <div className="ml-5">
                          <DescriptionEditor
                            value={table.description}
                            onSave={async (desc) => {
                              await handleSaveDescription(table.id, null, desc)
                              setSchema(prev => prev.map(t => t.id === table.id ? { ...t, description: desc } : t))
                              loadStatus()
                            }}
                            placeholder={t('dbSchema.addDescZh')}
                          />
                        </div>
                      </div>

                      {/* Columns */}
                      {expandedTables.has(table.id) && (
                        <div className="ml-5 pb-3">
                          {table.columns.length === 0 ? (
                            <div className="px-4 py-2 text-xs text-ink-lighter font-kai">{t('dbSchema.noFields')}</div>
                          ) : (
                            <div className="space-y-0.5">
                              {table.columns.map(col => (
                                <div key={col.id} className="px-4 py-1.5 flex items-start gap-3 hover:bg-smoke/30 transition-colors rounded-sm">
                                  <div className="flex items-center gap-1.5 min-w-0 flex-1">
                                    <span className="text-xs font-medium text-ink whitespace-nowrap">{col.column_name}</span>
                                    <span className="text-[10px] text-ink-lighter/60 whitespace-nowrap font-mono">{col.data_type}</span>
                                    {col.is_primary_key && (
                                      <span className="text-[10px] text-amber bg-amber/10 px-1 rounded-sm">PK</span>
                                    )}
                                    {!col.is_nullable && (
                                      <span className="text-[10px] text-ink-lighter/40">NOT NULL</span>
                                    )}
                                  </div>
                                  <div className="flex-1 max-w-md">
                                    <DescriptionEditor
                                      value={col.description}
                                      onSave={async (desc) => {
                                        await handleSaveDescription(table.id, col.id, desc)
                                        setSchema(prev => prev.map(t =>
                                          t.id === table.id ? {
                                            ...t,
                                            columns: t.columns.map(c =>
                                              c.id === col.id ? { ...c, description: desc } : c
                                            ),
                                          } : t
                                        ))
                                        loadStatus()
                                      }}
                                      placeholder={t('dbSchema.addDescZh')}
                                    />
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Add Database Modal */}
      <DBConnectModal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        onConnected={() => {
          setShowAddModal(false)
          loadDatabasesList()
        }}
      />
    </div>
  )
}
