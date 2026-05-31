import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { QueryResultInfo } from '../types'
import ChartRenderer from './ChartRenderer'

interface MarkdownRendererProps {
  content: string
  className?: string
  queryResults?: QueryResultInfo[]
}

/**
 * Markdown 渲染器组件
 * 支持 GFM 表格和代码高亮，并处理特殊的 [Qn] 标记
 */
const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, className = '', queryResults = [] }) => {
  return (
    <div className={`markdown-body ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // 处理代码块高亮
          code({ node, inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || '')
            return !inline && match ? (
              <SyntaxHighlighter
                style={oneLight}
                language={match[1]}
                PreTag="div"
                className="rounded-md my-2"
                {...props}
              >
                {String(children).replace(/\n$/, '')}
              </SyntaxHighlighter>
            ) : (
              <code className={`${className} bg-smoke text-celadon-dark px-1 py-0.5 rounded text-[0.8em] font-mono`} {...props}>
                {children}
              </code>
            )
          },
          // 处理表格样式
          table({ children }) {
            return <table className="query-table my-2 w-full">{children}</table>
          },
          // 处理文本节点，识别 [Qn]
          // 注意：在 react-markdown 9+ 中，text 组件的处理方式有所不同
          // 这里我们通过处理 p, li 等容器组件中的 children 来实现更可靠的替换
          p({ children }) {
            return <p>{processChildren(children, queryResults)}</p>
          },
          li({ children }) {
            return <li>{processChildren(children, queryResults)}</li>
          }
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

/**
 * 处理组件的子节点，识别并替换 [Qn] 标记
 */
function processChildren(children: React.ReactNode, queryResults: QueryResultInfo[]): React.ReactNode {
  return React.Children.map(children, child => {
    if (typeof child === 'string') {
      const parts = []
      let lastIndex = 0
      const regex = /\[Q(\d+)\]/g
      let match

      while ((match = regex.exec(child)) !== null) {
        if (match.index > lastIndex) {
          const text = child.substring(lastIndex, match.index)
          parts.push(<span key={`text-${lastIndex}`}>{text}</span>)
        }
        
        const qn = parseInt(match[1])
        const result = queryResults.find(r => r.qn === qn)
        parts.push(<QueryBadge key={`badge-${match.index}`} qn={qn} result={result} />)
        lastIndex = regex.lastIndex
      }

      if (lastIndex < child.length) {
        const text = child.substring(lastIndex)
        parts.push(<span key={`text-${lastIndex}`}>{text}</span>)
      }
      
      return parts.length > 0 ? <>{parts}</> : child
    }
    return child
  })
}

/**
 * 查询徽章组件
 * 显示 [Qn] 并提供图表切换功能
 */
function QueryBadge({ qn, result }: { qn: number, result?: QueryResultInfo }) {
  const { t } = useTranslation()
  const [showChart, setShowChart] = useState(false)
  
  const canShowChart = !!(result?.ok && result.data && result.columns && result.columns.length >= 2)
  
  return (
    <span className="inline-block align-middle">
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-celadon/10 text-celadon-dark text-[10px] font-bold leading-none mx-0.5 border border-celadon/20">
        <span>Q{qn}</span>
        {canShowChart && (
          <button 
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); setShowChart(!showChart) }}
            className="hover:text-celadon transition-colors ml-0.5"
            title={showChart ? t('chart.switchToTable') : t('chart.switchToChart')}
          >
            {showChart ? (
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <line x1="3" y1="9" x2="21" y2="9" />
                <line x1="3" y1="15" x2="21" y2="15" />
                <line x1="9" y1="9" x2="9" y2="21" />
              </svg>
            ) : (
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                <path d="M21.21 15.89A10 10 0 1 1 8 2.83" />
                <path d="M22 12A10 10 0 0 0 12 2v10z" />
              </svg>
            )}
          </button>
        )}
      </span>
      {showChart && canShowChart && (
        <span className="block w-full min-w-[300px] my-2">
          <ChartRenderer 
            columns={result.columns!} 
            data={result.data!} 
            title={result.question || `查询 Q${qn} 的图表可视化`} 
          />
        </span>
      )}
    </span>
  )
}

export default MarkdownRenderer
