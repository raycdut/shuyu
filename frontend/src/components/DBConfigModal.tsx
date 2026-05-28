import { useState } from 'react'
import { api } from '../api'

interface DBConfigModalProps {
  open: boolean
  db: { id: string; name: string; include_tables?: string[] | null; exclude_tables?: string[] | null; path?: string } | null
  onClose: () => void
  onSaved: () => void
}

export default function DBConfigModal({ open, db, onClose, onSaved }: DBConfigModalProps) {
  const [includeText, setIncludeText] = useState((db?.include_tables || []).join(', '))
  const [excludeText, setExcludeText] = useState((db?.exclude_tables || []).join(', '))
  const [saving, setSaving] = useState(false)

  if (!open || !db) return null

  const handleSave = async () => {
    setSaving(true)
    try {
      // Parse comma-separated patterns
      const includes = includeText.split(',').map(s => s.trim()).filter(Boolean)
      const excludes = excludeText.split(',').map(s => s.trim()).filter(Boolean)

      // Save via PATCH API
      await fetch(`/api/database/${db.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ include_tables: includes, exclude_tables: excludes }),
      })
      onSaved()
      onClose()
    } catch { /* 静默 */ }
    setSaving(false)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20" onClick={onClose}>
      <div className="bg-paper-light paper-shadow-md rounded-sm p-5 max-w-md w-full mx-4" onClick={e => e.stopPropagation()}>
        <h3 className="text-sm font-medium text-ink mb-1">数据库配置 — {db.name}</h3>
        <p className="text-xs text-ink-lighter mb-4 font-kai">设置表过滤规则（留空表示不过滤）</p>

        <label className="block text-xs text-ink-lighter mb-1 font-kai">路径</label>
        <input
          className="w-full px-2 py-1.5 text-xs text-ink bg-white ink-border rounded-sm mb-3"
          value={db.path || ''}
          disabled
        />

        <label className="block text-xs text-ink-lighter mb-1 font-kai">仅包含这些表（逗号分隔，支持 * 通配符）</label>
        <input
          className="w-full px-2 py-1.5 text-sm text-ink bg-white ink-border rounded-sm mb-3"
          value={includeText}
          onChange={e => setIncludeText(e.target.value)}
          placeholder="fct_*, dim_*"
        />

        <label className="block text-xs text-ink-lighter mb-1 font-kai">排除这些表（逗号分隔）</label>
        <input
          className="w-full px-2 py-1.5 text-sm text-ink bg-white ink-border rounded-sm mb-4"
          value={excludeText}
          onChange={e => setExcludeText(e.target.value)}
          placeholder="temp_*, _internal"
        />

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-sm text-ink-light hover:bg-smoke rounded-sm transition-colors"
          >取消</button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-3 py-1.5 text-sm text-white bg-celadon hover:bg-celadon-dark rounded-sm transition-colors disabled:opacity-40"
          >{saving ? '保存中…' : '保存'}</button>
        </div>
      </div>
    </div>
  )
}
