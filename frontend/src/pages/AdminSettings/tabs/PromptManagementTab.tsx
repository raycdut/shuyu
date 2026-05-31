import { useState, useEffect, useCallback } from 'react'
import { api } from '../../../api'
import type { PromptListItem, ActivePromptsResponse } from '../../../types'

const AGENT_TABS = [
  {
    key: 'basic',
    label: '数据分析 Agent',
    items: [
      { key: 'system', name: '系统提示词' },
      { key: 'sql_gen', name: 'SQL 生成提示词' },
    ],
  },
  {
    key: 'advanced',
    label: '深度分析 Agent',
    items: [
      { key: 'plan', name: '规划提示词' },
      { key: 'plan_reflect', name: '规划审核提示词' },
      { key: 'report_reflect', name: '报告审核提示词' },
    ],
  },
  {
    key: 'schema',
    label: 'Schema 描述 Agent',
    items: [
      { key: 'schema_describe', name: '描述生成提示词' },
    ],
  },
]

type EditorState = {
  category: string
  displayName: string
  content: string
  currentVersion: number | null
  currentId: number | null
  versions: PromptListItem[]
}

function formatTime(ts: number): string {
  const d = new Date(ts * 1000)
  return d.toLocaleDateString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

function PromptCard({
  name,
  category,
  active,
  onEdit,
}: {
  name: string
  category: string
  active: { id: number | null; content: string; version: number | null } | undefined
  onEdit: (category: string, displayName: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const content = active?.content ?? ''
  const preview = content.length > 300 ? content.slice(0, 300) + '…' : content
  const fullPreview = content

  return (
    <div className="bg-white/80 rounded-sm border border-tea/20 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="text-sm font-kai font-semibold text-ink">{name}</span>
          {active?.version ? (
            <span className="text-xs text-celadon font-mono bg-celadon/10 px-2 py-0.5 rounded-sm">
              v{active.version} ✓
            </span>
          ) : (
            <span className="text-xs text-ink-lighter font-mono bg-tea/10 px-2 py-0.5 rounded-sm">默认</span>
          )}
        </div>
        <button
          onClick={() => onEdit(category, name)}
          className="text-xs text-celadon hover:text-celadon-dark transition-colors font-kai border border-celadon/30 rounded-sm px-3 py-1 hover:bg-celadon/5"
        >
          编辑
        </button>
      </div>

      <div className="relative">
        <pre className={`text-xs font-mono text-ink-light bg-paper-light rounded-sm p-3 border border-tea/10 overflow-x-auto whitespace-pre-wrap break-words ${expanded ? 'max-h-none' : 'max-h-32 overflow-y-hidden'}`}>
          {expanded ? fullPreview : preview}
        </pre>
        {content.length > 300 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-1 text-xs text-celadon hover:text-celadon-dark transition-colors font-kai"
          >
            {expanded ? '收起' : '展开全部'}
          </button>
        )}
      </div>
    </div>
  )
}

export function PromptManagementTab() {
  const [activeTab, setActiveTab] = useState('basic')
  const [activePrompts, setActivePrompts] = useState<ActivePromptsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [editor, setEditor] = useState<EditorState | null>(null)
  const [saving, setSaving] = useState(false)
  const [editingContent, setEditingContent] = useState('')

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getActivePrompts()
      setActivePrompts(data)
    } catch (e) {
      console.error('Failed to load prompts:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const openEditor = useCallback(async (category: string, displayName: string) => {
    try {
      const [activeData, listData] = await Promise.all([
        api.getActivePrompts(),
        api.getPrompts(category),
      ])
      const active = activeData[category]
      const content = active?.content ?? ''
      setEditor({
        category,
        displayName,
        content,
        currentVersion: active?.version ?? null,
        currentId: active?.id ?? null,
        versions: listData.prompts.filter(v => v.id !== active?.id),
      })
      setEditingContent(content)
    } catch (e) {
      console.error('Failed to load prompt:', e)
    }
  }, [])

  const handleSave = useCallback(async () => {
    if (!editor) return
    setSaving(true)
    try {
      const result = await api.upsertPrompt(editor.category, editingContent)
      if (result.ok) {
        await loadData()
        setEditor(prev => prev ? {
          ...prev,
          content: editingContent,
          currentVersion: result.version,
        } : null)
      }
    } catch (e: any) {
      alert('保存失败: ' + e.message)
    } finally {
      setSaving(false)
    }
  }, [editor, editingContent, loadData])

  const handleActivate = useCallback(async (id: number) => {
    if (!editor) return
    try {
      const result = await api.activatePrompt(id)
      if (result.ok) {
        await loadData()
        const [activeData, listData] = await Promise.all([
          api.getActivePrompts(),
          api.getPrompts(editor.category),
        ])
        const active = activeData[editor.category]
        setEditor({
          ...editor,
          content: active?.content ?? '',
          currentVersion: active?.version ?? null,
          currentId: active?.id ?? null,
          versions: listData.prompts.filter(v => v.id !== active?.id),
        })
        setEditingContent(active?.content ?? '')
      }
    } catch (e: any) {
      alert('操作失败: ' + e.message)
    }
  }, [editor])

  const handleResetDefault = useCallback(async () => {
    if (!editor) return
    try {
      const data = await api.getDefaultPrompt(editor.category)
      if (data.content) {
        setEditingContent(data.content)
      }
    } catch (e: any) {
      alert('获取默认提示词失败: ' + e.message)
    }
  }, [editor])

  const closeEditor = useCallback(() => {
    setEditor(null)
  }, [])

  const currentGroup = AGENT_TABS.find(t => t.key === activeTab)

  if (loading) {
    return <div className="py-12 text-center text-ink-lighter font-kai">加载中…</div>
  }

  return (
    <div>
      <h2 className="text-lg font-song font-bold text-ink mb-4">Prompt 管理</h2>

      <div className="flex gap-1 mb-6 border-b border-tea/20">
        {AGENT_TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-5 py-2.5 text-sm font-kai transition-colors rounded-t-sm ${
              activeTab === tab.key
                ? 'text-celadon border-b-2 border-celadon bg-celadon/5'
                : 'text-ink-light hover:text-ink hover:bg-smoke/40'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="space-y-4">
        {currentGroup?.items.map(item => (
          <PromptCard
            key={item.key}
            name={item.name}
            category={item.key}
            active={activePrompts?.[item.key]}
            onEdit={openEditor}
          />
        ))}
      </div>

      {editor && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={closeEditor}>
          <div className="bg-white rounded-sm shadow-xl w-full max-w-3xl max-h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-tea/20">
              <div>
                <h3 className="text-sm font-kai font-semibold text-ink">编辑 {editor.displayName}</h3>
                <p className="text-xs text-ink-lighter mt-0.5">
                  {editor.category}
                  {editor.currentVersion != null && (
                    <span className="ml-2">· 当前版本 v{editor.currentVersion}</span>
                  )}
                </p>
              </div>
              <button onClick={closeEditor} className="text-ink-lighter hover:text-ink transition-colors">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6">
              <textarea
                value={editingContent}
                onChange={e => setEditingContent(e.target.value)}
                className="w-full h-64 p-4 border border-tea/30 rounded-sm text-sm font-mono text-ink bg-paper-light resize-none focus:outline-none focus:border-celadon/50 focus:ring-1 focus:ring-celadon/20"
                spellCheck={false}
              />

              <div className="flex items-center justify-between mt-4">
                <div className="flex gap-3">
                  <button
                    onClick={handleResetDefault}
                    className="px-4 py-2 text-xs text-ink-light bg-smoke/50 rounded-sm hover:bg-smoke transition-colors font-kai"
                  >
                    恢复默认
                  </button>
                </div>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="px-5 py-2 text-xs text-white bg-celadon rounded-sm hover:bg-celadon/90 transition-colors font-kai disabled:opacity-50"
                >
                  {saving ? '保存中…' : '保存为新版本'}
                </button>
              </div>

              <div className="mt-6 pt-4 border-t border-tea/10">
                <h4 className="text-xs text-ink-lighter font-kai mb-2">版本历史</h4>
                {editor.versions.length === 0 ? (
                  <p className="text-xs text-ink-lighter/60 font-kai">暂无其他版本</p>
                ) : (
                  <div className="space-y-1 max-h-48 overflow-y-auto">
                    {editor.versions.map(v => (
                      <div
                        key={v.id}
                        className={`flex items-center justify-between p-2 rounded-sm text-xs ${
                          v.is_active ? 'bg-celadon/5 border border-celadon/20' : 'hover:bg-smoke/40'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-ink">v{v.version}</span>
                          {v.is_active && <span className="text-celadon">✓ 当前</span>}
                          <span className="text-ink-lighter">{formatTime(v.created_at)}</span>
                        </div>
                        {!v.is_active && (
                          <button
                            onClick={() => handleActivate(v.id)}
                            className="text-celadon hover:text-celadon-dark transition-colors"
                          >
                            设为此版本
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}