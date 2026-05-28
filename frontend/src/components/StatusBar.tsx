interface StatusBarProps {
  llmModel: string
  llmConnected: boolean | null
  dbName: string
  sessionTitle?: string
}

export default function StatusBar({ llmModel, llmConnected, dbName, sessionTitle }: StatusBarProps) {
  return (
    <footer className="flex-shrink-0 flex items-center justify-between px-4 py-1.5 bg-white/70 ink-border border-b-0 border-x-0 text-[11px] text-ink-lighter">
      <div className="flex items-center gap-4">
        {sessionTitle && (
          <span className="flex items-center gap-1">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            <span className="max-w-[200px] truncate">{sessionTitle}</span>
          </span>
        )}
      </div>
      <div className="flex items-center gap-4">
        <span className="flex items-center gap-1">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <ellipse cx="12" cy="5" rx="9" ry="3" />
            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
          </svg>
          <span className="font-medium text-ink-light">{dbName}</span>
        </span>

        {/* 模型 + 连接状态指示灯 */}
        <span className="flex items-center gap-1.5">
          {/* 状态圆点 */}
          <span
            className={`inline-block w-2 h-2 rounded-full transition-colors duration-300 ${
              llmConnected === null
                ? 'bg-ink-lighter/30'
                : llmConnected
                  ? 'bg-green-500 shadow-[0_0_4px_rgba(34,197,94,0.5)]'
                  : 'bg-ink-lighter/40'
            }`}
            title={
              llmConnected === null
                ? '检测中…'
                : llmConnected
                  ? '已连接'
                  : '未连接'
            }
          />
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="4" y="4" width="16" height="16" rx="2" />
            <path d="M9 9h.01M15 9h.01M9 15h6" />
          </svg>
          <span>{llmModel}</span>
        </span>
      </div>
    </footer>
  )
}
