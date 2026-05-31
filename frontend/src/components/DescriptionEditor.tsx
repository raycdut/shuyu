import { useState, useRef, useEffect } from 'react'

interface DescriptionEditorProps {
  value: string
  onSave: (value: string) => Promise<void>
  placeholder?: string
  className?: string
}

export default function DescriptionEditor({ value, onSave, placeholder, className = '' }: DescriptionEditorProps) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(value)
  const [saving, setSaving] = useState(false)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    setText(value)
  }, [value])

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [editing])

  const handleSave = async () => {
    if (text === value) {
      setEditing(false)
      return
    }
    setSaving(true)
    try {
      await onSave(text)
    } catch {
      setText(value)
    }
    setSaving(false)
    setEditing(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSave()
    }
    if (e.key === 'Escape') {
      setText(value)
      setEditing(false)
    }
  }

  if (editing) {
    return (
      <div className="flex flex-col gap-1">
        <textarea
          ref={inputRef}
          value={text}
          onChange={e => setText(e.target.value)}
          onBlur={handleSave}
          onKeyDown={handleKeyDown}
          className={`w-full px-2 py-1 text-xs bg-white ink-border rounded-sm resize-none focus:outline-none focus:border-celadon ${className}`}
          rows={2}
          placeholder={placeholder}
        />
        {saving && <span className="text-[10px] text-ink-lighter">保存中…</span>}
      </div>
    )
  }

  return (
    <div
      onClick={() => setEditing(true)}
      className={`group cursor-text ${className}`}
    >
      {value ? (
        <span className="text-xs text-ink leading-relaxed">{value}</span>
      ) : (
        <span className="text-xs text-ink-lighter/60 italic group-hover:text-ink-lighter transition-colors">
          {placeholder || '点击添加描述…'}
        </span>
      )}
      <span className="ml-1 text-[10px] text-ink-lighter/40 group-hover:text-ink-lighter/70 transition-colors">
        ✎
      </span>
    </div>
  )
}
