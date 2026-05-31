import React, { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUIStore } from '../store/uiStore'
import { api } from '../api'
import ChartRenderer from './ChartRenderer'

const Dashboard: React.FC = () => {
  const dashboardItems = useUIStore(s => s.dashboardItems)
  const removeDashboardItem = useUIStore(s => s.removeDashboardItem)
  const setDashboardItems = useUIStore(s => s.setDashboardItems)
  const navigate = useNavigate()

  useEffect(() => {
    api.getDashboardItems().then((items) => {
      setDashboardItems(items.map(item => ({
        id: item.id,
        title: item.title,
        columns: item.chart_data?.columns || [],
        data: item.chart_data?.data || [],
        type: item.chart_type as 'line' | 'bar' | 'table',
        createdAt: item.created_at * 1000,
      })))
    }).catch(() => {
      // Silent fail — items already loaded from memory
    })
  }, [setDashboardItems])

  const handleRemove = async (id: string) => {
    try {
      await api.removeDashboardItem(id)
      removeDashboardItem(id)
    } catch {
      // Silent fail
    }
  }

  if (dashboardItems.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-paper/30 p-8 text-center">
        <div className="text-4xl mb-4 opacity-20">📌</div>
        <h2 className="text-lg font-song text-ink-light mb-2">看板还是空的</h2>
        <p className="text-sm text-ink-lighter font-kai mb-6 max-w-md">
          在对话中点击查询标记旁的"固定"按钮，将重要的查询结果保存到这里。
        </p>
        <button
          onClick={() => navigate('/')}
          className="px-4 py-2 bg-celadon text-white rounded-md text-sm hover:bg-celadon-dark transition-colors"
        >
          返回对话
        </button>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-paper/30">
      <header className="flex-shrink-0 flex items-center justify-between px-6 py-4 bg-white/60 border-b border-tea/50">
        <div className="flex items-center gap-2">
          <span className="text-lg">📌</span>
          <h2 className="text-lg font-song font-semibold text-ink">数据看板</h2>
          <span className="text-xs text-ink-lighter ml-2">已固定 {dashboardItems.length} 个条目</span>
        </div>
        <button
          onClick={() => navigate('/')}
          className="text-sm text-celadon hover:underline font-medium"
        >
          返回对话
        </button>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {dashboardItems.map((item) => (
            <div key={item.id} className="bg-white rounded-xl ink-border p-4 flex flex-col shadow-sm hover:shadow-md transition-shadow group relative">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-ink truncate flex-1" title={item.title}>
                  {item.title}
                </h3>
                <button
                  onClick={() => handleRemove(item.id)}
                  className="opacity-0 group-hover:opacity-100 p-1 text-ink-lighter hover:text-cinnabar transition-all"
                  title="移除"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                  </svg>
                </button>
              </div>

              <div className="flex-1 min-h-[200px] flex items-center justify-center">
                {item.type === 'table' ? (
                  <div className="w-full overflow-hidden">
                    <table className="query-table text-[10px] w-full">
                      <thead>
                        <tr>
                          {item.columns.slice(0, 3).map((col, i) => <th key={i}>{col}</th>)}
                          {item.columns.length > 3 && <th>...</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {item.data.slice(0, 5).map((row, ri) => (
                          <tr key={ri}>
                            {row.slice(0, 3).map((cell, ci) => <td key={ci}>{String(cell)}</td>)}
                            {item.columns.length > 3 && <td>...</td>}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {item.data.length > 5 && (
                      <div className="text-[10px] text-ink-lighter mt-2 text-center">
                        还有 {item.data.length - 5} 行数据...
                      </div>
                    )}
                  </div>
                ) : (
                  <ChartRenderer columns={item.columns} data={item.data} />
                )}
              </div>
              
              <div className="mt-3 pt-2 border-t border-tea/20 text-[10px] text-ink-lighter flex justify-between">
                <span>{new Date(item.createdAt).toLocaleString()}</span>
                <span className="capitalize">{item.type}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default Dashboard
