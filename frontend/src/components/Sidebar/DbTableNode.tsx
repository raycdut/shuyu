import React, { useState } from 'react'
import type { SchemaTable } from '../../types'

interface DbTableNodeProps {
  table: SchemaTable
}

/**
 * 数据库表树节点组件
 * 以树形结构展示数据表的列信息，支持展开/折叠
 */
const DbTableNode = React.memo(function DbTableNode({ table }: DbTableNodeProps) {
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
})

export default DbTableNode
