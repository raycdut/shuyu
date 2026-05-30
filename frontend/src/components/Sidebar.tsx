import React, { useState, useRef } from 'react'
import type { Session, DatabaseInfo, SchemaTable } from '../types'
import { api } from '../api'
import DBConnectModal from './DBConnectModal'
import DBConfigModal from './DBConfigModal'

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
  const [showDBModal, setShowDBModal] = useState(false)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [showClearConfirm, setShowClearConfirm] = useState(false)
  const [expandedDb, setExpandedDb] = useState<string | null>(null)
  const [dbTrees, setDbTrees] = useState<Record<string, SchemaTable[]>>({})
  const [loadingTree, setLoadingTree] = useState<string | null>(null)
  const [configDb, setConfigDb] = useState<DatabaseInfo | null>(null)

  // --- 分组会话 ---
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

  // --- 树展开/收起 ---
  const toggleDbTree = async (dbId: string) => {
    // 点击时标记为当前数据库
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

  // --- 删除 ---
  const handleDelete = (id: string) => {
    onDeleteSession(id)
    setConfirmDeleteId(null)
  }

  // --- 数据库图标 ---
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
        {/* ===== 会话列表 ===== */}
        <div className="flex-1 overflow-y-auto">
          <div className="flex items-center justify-between px-3 py-2">
            <span className="text-xs text-ink-lighter font-kai tracking-wider">历史会话</span>
            <div className="flex items-center gap-1">
              {sessions.length > 0 && (
                <button
                  onClick={() => setShowClearConfirm(true)}
                  aria-label="清空所有会话"
                  className="p-1 rounded-sm text-ink-lighter hover:text-cinnabar hover:bg-smoke transition-colors"
                  title="清空所有会话"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                  </svg>
                </button>
              )}
              <button
                onClick={onNewSession}
                aria-label="新建会话"
                className="p-1 rounded-sm text-ink-light hover:text-celadon hover:bg-smoke transition-colors"
                title="新建会话"
              >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
              </svg>
            </button>
            </div>
          </div>

          {today.length > 0 && (
            <>{sectionTitle('今天')}{today.map(s => <SessionItem key={s.id} session={s} isActive={s.id === activeSessionId} onSelectSession={onSelectSession} onRenameSession={onRenameSession} onRequestDelete={(id) => setConfirmDeleteId(id)} />)}</>
          )}
          {thisWeek.length > 0 && (
            <>{sectionTitle('本周')}{thisWeek.map(s => <SessionItem key={s.id} session={s} isActive={s.id === activeSessionId} onSelectSession={onSelectSession} onRenameSession={onRenameSession} onRequestDelete={(id) => setConfirmDeleteId(id)} />)}</>
          )}
          {earlier.length > 0 && (
            <>{sectionTitle('更早')}{earlier.map(s => <SessionItem key={s.id} session={s} isActive={s.id === activeSessionId} onSelectSession={onSelectSession} onRenameSession={onRenameSession} onRequestDelete={(id) => setConfirmDeleteId(id)} />)}</>
          )}
          {sessions.length === 0 && (
            <div className="px-3 py-6 text-center text-xs text-ink-lighter font-kai">暂无历史会话</div>
          )}
        </div>

        {/* ===== 分隔线 ===== */}
        <div className="ink-divider mx-3" />

        {/* ===== 数据库列表（树状） ===== */}
        <div className="flex-shrink-0 overflow-y-auto max-h-64">
          <div className="px-3 py-2 flex items-center justify-between">
            <span className="text-xs text-ink-lighter font-kai tracking-wider">数据库</span>
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
                aria-label="刷新数据库列表"
                className="p-1 rounded-sm text-ink-lighter hover:text-celadon hover:bg-smoke transition-colors"
                title="刷新数据库列表"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="23 4 23 10 17 10" />
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                </svg>
              </button>
            )}
          </div>
          {databases.length === 0 ? (
            <div className="px-3 py-2 text-xs text-ink-lighter font-kai">尚未添加数据库</div>
          ) : (
            databases.map(db => (
              <div key={db.id} className="relative group">
                {/* 数据库行 */}
                {/* 数据库行：可点击展开 */}
                <button
                  onClick={() => toggleDbTree(db.id)}
                  className={`w-full text-left px-3 py-1 text-sm flex items-center gap-1.5 transition-colors
                    ${activeDbId === db.id ? 'bg-celadon/10 text-celadon-dark font-medium' : 'text-ink-light hover:bg-smoke'}`}
                >
                  {/* 三角形箭头 */}
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
                {/* 齿轮按钮 */}
                <button
                  onClick={(e) => { e.stopPropagation(); setConfigDb(db) }}
                  aria-label="数据库配置"
                  className="absolute right-1 top-1/2 -translate-y-1/2 p-0.5 rounded-sm
                    opacity-0 group-hover:opacity-100
                    text-ink-lighter hover:text-celadon hover:bg-smoke
                    transition-all duration-200"
                  title="数据库配置"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="3" width="7" height="7" rx="1" />
                    <rect x="14" y="14" width="7" height="7" rx="1" />
                    <rect x="14" y="3" width="7" height="7" rx="1" />
                    <rect x="3" y="14" width="7" height="7" rx="1" />
                  </svg>
                </button>

                {/* 表树 */}
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

          <button
            onClick={() => setShowDBModal(true)}
            className="w-full text-left px-3 py-1.5 text-sm text-ink-lighter hover:text-celadon hover:bg-smoke transition-colors flex items-center gap-2"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            添加数据库
          </button>
        </div>
      </aside>

      {/* 数据库连接弹窗 */}
      <DBConnectModal
        open={showDBModal}
        onClose={() => setShowDBModal(false)}
        onConnected={() => {
          setShowDBModal(false)
          onDatabasesChange()
        }}
      />

      {/* 数据库配置弹窗 */}
      <DBConfigModal
        open={configDb !== null}
        db={configDb}
        onClose={() => setConfigDb(null)}
        onSaved={() => {
          setConfigDb(null)
          onDatabasesChange()
        }}
      />

      {/* 删除确认 */}
      {confirmDeleteId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20">
          <div className="bg-paper-light paper-shadow-md rounded-sm p-6 max-w-sm">
            <p className="text-sm text-ink mb-4">确定要删除这个会话吗？此操作不可恢复。</p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setConfirmDeleteId(null)} className="px-3 py-1.5 text-sm text-ink-light hover:bg-smoke rounded-sm transition-colors">取消</button>
              <button onClick={() => handleDelete(confirmDeleteId)} className="px-3 py-1.5 text-sm text-white bg-cinnabar hover:bg-cinnabar-light rounded-sm transition-colors">删除</button>
            </div>
          </div>
        </div>
      )}

      {/* 清空所有会话确认 */}
      {showClearConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20" onClick={() => setShowClearConfirm(false)}>
          <div className="bg-paper-light paper-shadow-md rounded-sm p-6 max-w-sm mx-4" onClick={e => e.stopPropagation()}>
            <p className="text-sm text-ink mb-2">确定要清空所有会话？</p>
            <p className="text-xs text-ink-lighter mb-4 font-kai">此操作不可恢复，共 {sessions.length} 个会话将被删除。</p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setShowClearConfirm(false)} className="px-3 py-1.5 text-sm text-ink-light hover:bg-smoke rounded-sm transition-colors">取消</button>
              <button onClick={async () => {
                try {
                  await fetch('/api/sessions', { method: 'DELETE' })
                  setShowClearConfirm(false)
                  if (onClearAllSessions) onClearAllSessions()
                } catch { /* ignore */ }
              }} className="px-3 py-1.5 text-sm text-white bg-cinnabar hover:bg-cinnabar-light rounded-sm transition-colors">清空</button>
            </div>
          </div>
        </div>
      )}
    </>
  )

})

export default Sidebar

// ===== 表树节点 =====
function DbTableNode({ table }: { table: SchemaTable }) {
  const [expanded, setExpanded] = useState(true)

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left px-2 py-0.5 text-xs text-ink-light hover:bg-smoke transition-colors flex items-center gap-1"
      >
        <span className="text-[9px] w-2.5 text-center text-ink-lighter transition-transform duration-150"
          style={{ transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>
          ▶
        </span>
        <span className="text-[11px]">{table.type === 'VIEW' ? '👁' : '📋'}</span>
        <span className="font-medium">{table.name}</span>
      </button>
      {expanded && (
        <div className="ml-4 border-l border-tea/30">
          {table.columns.map(col => (
            <div key={col.name} className="px-2 py-[2px] text-[11px] text-ink-lighter hover:bg-smoke flex gap-2">
              <span className="text-tea">├─</span>
              <span>{col.name}</span>
              <span className="text-[10px] text-ink-lighter/60">{col.type}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ===== 会话条目 =====
const SessionItem = React.memo(function SessionItem({
  session,
  isActive,
  onSelectSession,
  onRenameSession,
  onRequestDelete,
}: {
  session: Session
  isActive: boolean
  onSelectSession: (id: string) => void
  onRenameSession: (id: string, title: string) => void
  onRequestDelete: (id: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [editTitle, setEditTitle] = useState(session.title || '')
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDoubleClick = () => {
    setEditing(true)
    setEditTitle(session.title || '')
    setTimeout(() => inputRef.current?.select(), 50)
  }

  const handleConfirm = () => {
    if (editTitle.trim()) {
      onRenameSession(session.id, editTitle.trim())
    }
    setEditing(false)
  }

  return (
    <div className="relative group">
      {editing ? (
        <input
          ref={inputRef}
          className="w-full px-3 py-1.5 text-sm bg-white ink-border rounded-sm focus:outline-none focus:border-celadon"
          value={editTitle}
          onChange={e => setEditTitle(e.target.value)}
          onBlur={handleConfirm}
          onKeyDown={e => {
            if (e.key === 'Enter') handleConfirm()
            if (e.key === 'Escape') setEditing(false)
          }}
        />
      ) : (
        <button
          onClick={() => onSelectSession(session.id)}
          onDoubleClick={handleDoubleClick}
          className={`w-full text-left px-3 py-1.5 text-sm truncate transition-colors
            ${isActive ? 'bg-celadon/10 text-celadon-dark font-medium' : 'text-ink-light hover:bg-smoke'}`}
        >
          <span>{session.title || '新对话'}</span>
          <span className="ml-2 text-xs text-ink-lighter">{session.messages}</span>
        </button>
      )}
      {!editing && (
        <button
          onClick={(e) => { e.stopPropagation(); onRequestDelete(session.id) }}
          aria-label="删除会话"
          className="absolute right-1 top-1/2 -translate-y-1/2 p-0.5 rounded-sm opacity-0 group-hover:opacity-100 text-ink-lighter hover:text-cinnabar hover:bg-smoke transition-all duration-200"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>
        </button>
      )}
    </div>
  )
})
