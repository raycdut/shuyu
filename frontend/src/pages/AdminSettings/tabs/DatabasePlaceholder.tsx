/**
 * 数据库管理占位组件
 */
export function DatabasePlaceholder() {
  return (
    <div className="w-full h-[400px] flex flex-col items-center justify-center border-2 border-dashed border-tea/30 rounded-lg bg-smoke/20 animate-in fade-in duration-500">
      <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center shadow-sm mb-4 border border-tea/20">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-tea">
          <ellipse cx="12" cy="5" rx="9" ry="3" />
          <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
          <path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3" />
        </svg>
      </div>
      <h3 className="text-lg font-song font-bold text-ink mb-1">数据库管理</h3>
      <p className="text-sm text-ink-lighter font-kai max-w-xs text-center">此功能正在深度设计中，未来将支持多数据库连接池、动态 Schema 刷新与权限审计</p>
    </div>
  )
}
