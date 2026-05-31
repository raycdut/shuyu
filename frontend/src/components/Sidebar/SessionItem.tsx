import React, { useState, useRef } from 'react'
import type { Session } from '../../types'

interface SessionItemProps {
  session: Session
  isActive: boolean
  onSelectSession: (id: string) => void
  onRenameSession: (id: string, title: string) => void
  onRequestDelete: (id: string) => void
}

/**
 * 会话条目组件
 * 显示单个会话的标题和消息数，支持双击重命名和悬停删除
 */
const SessionItem = React.memo(function SessionItem({
  session,
  isActive,
  onSelectSession,
  onRenameSession,
  onRequestDelete,
}: SessionItemProps) {
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

export default SessionItem
