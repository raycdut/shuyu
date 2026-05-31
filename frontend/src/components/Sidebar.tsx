import React, { useState, useCallback } from 'react'
import type { Session, DatabaseInfo, SchemaTable } from '../types'
import { api } from '../api'
import DBConfigModal from './DBConfigModal'
import SessionItem from './Sidebar/SessionItem'
import DbTableNode from './Sidebar/DbTableNode'
import { useTranslation } from 'react-i18next'

interface SidebarProps {
  open: boolean
  sessions: Session[]
  activeSessionId: string | null
  databases: DatabaseInfo[]
  activeDbId: string | null
  onSelectSession: (id: string) => void
  onNewSession: () => void
  onRenameSession: (id: string, title: string) => void
  onDeleteSession: (id: string) => void
  onSelectDb: (id: string | null) => void
  onDatabasesChange: () => void
  onClearAllSessions?: () => void
}

const Sidebar = React.memo(function Sidebar({
  open,
  sessions,
  activeSessionId,
  databases,
  activeDbId,
  onSelectSession,
  onNewSession,
  onRenameSession,
  onDeleteSession,
  onSelectDb,
  onDatabasesChange,
  onClearAllSessions,
}: SidebarProps) {
  const { t } = useTranslation()
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [showClearConfirm, setShowClearConfirm] = useState(false)
  const [expandedDb, setExpandedDb] = useState<string | null>(null)
  const [dbTrees, setDbTrees] = useState<Record<string, SchemaTable[]>>({})
  const [loadingTree, setLoadingTree] = useState<string | null>(null)
  const [configDb, setConfigDb] = useState<DatabaseInfo | null>(null)

  const handleRequestDelete = useCallback((id: string) => {
    setConfirmDeleteId(id)
  }, [])

  const now = Date.now()
  const day = 86400000
  const today: Session[] = []
  const thisWeek: Session[] = []
  const earlier: Session[] = []

  sessions.forEach((s) => {
    const t = s.last_active ? s.last_active * 1000 : now
    if (now - t < day) today.push(s)
    else if (now - t < 7 * day) thisWeek.push(s)
    else earlier.push(s)
  })

  const toggleDbTree = async (dbId: string) => {
    onSelectDb(dbId)
    if (expandedDb === dbId) {
      setExpandedDb(null)
      return
    }
    setExpandedDb(dbId)
    if (!dbTrees[dbId]) {
      setLoadingTree(dbId)
      try {
        const data = await api.getDatabaseTables(dbId)
        setDbTrees(prev => ({ ...prev, [dbId]: data.tables }))
      } catch {
        setDbTrees(prev => ({ ...prev, [dbId]: [] }))
      }
      setLoadingTree(null)
    }
  }

  const handleDelete = (id: string) => {
    onDeleteSession(id)
    setConfirmDeleteId(null)
  }

  const dbIcon = (type: string) => {
    switch (type) {
      case 'duckdb': return '🦆'
      case 'postgres': return '🐘'
      case 'sqlite': return '📄'
      case 'mysql': return '🐬'
      case 'clickhouse': return '🏠'
      case 'snowflake': return '❄️'
      default: return '🗄'
    }
  }

  const sectionTitle = (label: string) => (
    <div className="px-3 py-1.5 text-xs text-ink-lighter font-kai tracking-wider select-none">
      {label}
    </div>
  )

  if (!open) return null

  return (
    <>
      <aside className="w-56 flex-shrink-0 flex flex-col bg-paper-light/50 overflow-hidden">
        <div className="flex-1 overflow-y-auto">
          <div className="flex items-center justify-between px-3 py-2">
            <span className="text-xs text-ink-lighter font-kai tracking-wider">{t('sidebar.historySessions')}</span>
            <div className="flex items-center gap-1">
              {sessions.length > 0 && (
                <button
                  onClick={() => setShowClearConfirm(true)}
                  aria-label={t('sidebar.clearAllSessions')}
                  className="p-1 rounded-sm text-ink-lighter hover:text-cinnabar hover:bg-smoke transition-colors"
                  title={t('sidebar.clearAllSessions')}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                  </svg>
                </button>
              )}
              <button
                onClick={onNewSession}
                aria-label={t('sidebar.newSession')}
                className="p-1 rounded-sm text-ink-light hover:text-celadon hover:bg-smoke transition-colors"
                title={t('sidebar.newSession')}
              >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
              </svg>
            </button>
            </div>
          </div>

          {today.length > 0 && (
            <>{sectionTitle(t('sidebar.today'))}{today.map(s => <SessionItem key={s.id} session={s} isActive={s.id === activeSessionId} onSelectSession={onSelectSession} onRenameSession={onRenameSession} onRequestDelete={handleRequestDelete} />)}</>
          )}
          {thisWeek.length > 0 && (
            <>{sectionTitle(t('sidebar.thisWeek'))}{thisWeek.map(s => <SessionItem key={s.id} session={s} isActive={s.id === activeSessionId} onSelectSession={onSelectSession} onRenameSession={onRenameSession} onRequestDelete={handleRequestDelete} />)}</>
          )}
          {earlier.length > 0 && (
            <>{sectionTitle(t('sidebar.earlier'))}{earlier.map(s => <SessionItem key={s.id} session={s} isActive={s.id === activeSessionId} onSelectSession={onSelectSession} onRenameSession={onRenameSession} onRequestDelete={handleRequestDelete} />)}</>
          )}
          {sessions.length === 0 && (
            <div className="px-3 py-6 text-center text-xs text-ink-lighter font-kai">{t('sidebar.noHistorySessions')}</div>
          )}
        </div>

        <div className="ink-divider mx-3" />

        <div className="flex-shrink-0 overflow-y-auto max-h-64">
          <div className="px-3 py-2 flex items-center justify-between">
            <span className="text-xs text-ink-lighter font-kai tracking-wider">{t('sidebar.database')}</span>
            {databases.length > 0 && (
              <button
                onClick={() => {
                  setDbTrees({});
                  if (activeDbId) {
                    setExpandedDb(null);
                    setTimeout(() => toggleDbTree(activeDbId), 50);
                  } else {
                    setExpandedDb(null);
                    onDatabasesChange();
                  }
                }}
                aria-label={t('sidebar.refreshDatabaseList')}
                className="p-1 rounded-sm text-ink-lighter hover:text-celadon hover:bg-smoke transition-colors"
                title={t('sidebar.refreshDatabaseList')}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="23 4 23 10 17 10" />
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                </svg>
              </button>
            )}
          </div>
          {databases.length === 0 ? (
            <div className="px-3 py-2 text-xs text-ink-lighter font-kai">{t('sidebar.noDatabases')}</div>
          ) : (
            databases.map(db => (
              <div key={db.id} className="relative group">
                <button
                  onClick={() => toggleDbTree(db.id)}
                  className={`w-full text-left px-3 py-1 text-sm flex items-center gap-1.5 transition-colors
                    ${activeDbId === db.id ? 'bg-celadon/10 text-celadon-dark font-medium' : 'text-ink-light hover:bg-smoke'}`}
                >
                  <span className="text-[10px] w-3 text-center text-ink-lighter transition-transform duration-150"
                    style={{ transform: expandedDb === db.id ? 'rotate(90deg)' : 'rotate(0deg)' }}>
                    ▶
                  </span>
                  <span className="text-xs">{dbIcon(db.type)}</span>
                  <span className="truncate flex-1">{db.name}</span>
                  {loadingTree === db.id && (
                    <span className="text-[10px] text-ink-lighter animate-pulse">…</span>
                  )}
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); setConfigDb(db) }}
                  aria-label={t('sidebar.databaseConfig')}
                  className="absolute right-1 top-1/2 -translate-y-1/2 p-0.5 rounded-sm
                    opacity-0 group-hover:opacity-100
                    text-ink-lighter hover:text-celadon hover:bg-smoke
                    transition-all duration-200"
                  title={t('sidebar.databaseConfig')}
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="3" width="7" height="7" rx="1" />
                    <rect x="14" y="14" width="7" height="7" rx="1" />
                    <rect x="14" y="3" width="7" height="7" rx="1" />
                    <rect x="3" y="14" width="7" height="7" rx="1" />
                  </svg>
                </button>

                {expandedDb === db.id && dbTrees[db.id] && (
                  <div className="ml-4 border-l border-tea/40">
                    {dbTrees[db.id].map(tbl => (
                      <DbTableNode key={tbl.name} table={tbl} />
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </aside>

      <DBConfigModal
        open={configDb !== null}
        db={configDb}
        onClose={() => setConfigDb(null)}
        onSaved={() => {
          setConfigDb(null)
          onDatabasesChange()
        }}
      />

      {confirmDeleteId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20">
          <div className="bg-paper-light paper-shadow-md rounded-sm p-6 max-w-sm">
            <p className="text-sm text-ink mb-4">{t('sidebar.confirmDeleteSession')}</p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setConfirmDeleteId(null)} className="px-3 py-1.5 text-sm text-ink-light hover:bg-smoke rounded-sm transition-colors">取消</button>
              <button onClick={() => handleDelete(confirmDeleteId)} className="px-3 py-1.5 text-sm text-white bg-cinnabar hover:bg-cinnabar-light rounded-sm transition-colors">删除</button>
            </div>
          </div>
        </div>
      )}

      {showClearConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20" onClick={() => setShowClearConfirm(false)}>
          <div className="bg-paper-light paper-shadow-md rounded-sm p-6 max-w-sm mx-4" onClick={e => e.stopPropagation()}>
            <p className="text-sm text-ink mb-2">{t('sidebar.confirmClearAllSessions')}</p>
            <p className="text-xs text-ink-lighter mb-4 font-kai">{t('sidebar.clearAllHint', { count: sessions.length })}</p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setShowClearConfirm(false)} className="px-3 py-1.5 text-sm text-ink-light hover:bg-smoke rounded-sm transition-colors">{t('common.cancel')}</button>
              <button onClick={() => { setShowClearConfirm(false); if (onClearAllSessions) onClearAllSessions() }} className="px-3 py-1.5 text-sm text-white bg-cinnabar hover:bg-cinnabar-light rounded-sm transition-colors">{t('sidebar.confirmClear')}</button>
            </div>
          </div>
        </div>
      )}
    </>
  )

})

export default Sidebar
