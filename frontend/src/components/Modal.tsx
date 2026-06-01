import React from 'react'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  subtitle?: string
  children: React.ReactNode
  footer?: React.ReactNode
  size?: 'sm' | 'md' | 'lg' | 'xl'
  backdropBlur?: boolean
}

const SIZE_MAP: Record<string, string> = {
  sm: 'max-w-md',
  md: 'max-w-lg',
  lg: 'max-w-3xl',
  xl: 'max-w-4xl',
}

export function Modal({ open, onClose, title, subtitle, children, footer, size = 'md', backdropBlur }: ModalProps) {
  if (!open) return null
  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center ${backdropBlur ? 'bg-black/30 backdrop-blur-sm' : 'bg-black/20'}`}
      onClick={onClose}
    >
      <div
        className={`bg-white rounded-lg shadow-xl border border-tea/30 w-full ${SIZE_MAP[size]} mx-4 animate-in fade-in zoom-in-95 duration-200 flex flex-col max-h-[85vh]`}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-tea/20">
          <div>
            <h4 className="text-base font-song font-bold text-ink">{title}</h4>
            {subtitle && <p className="text-xs text-ink-lighter mt-0.5">{subtitle}</p>}
          </div>
          <button onClick={onClose} className="p-1 text-ink-lighter hover:text-ink transition-colors rounded-sm hover:bg-smoke">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="overflow-y-auto px-6 py-4">
          {children}
        </div>

        {footer && (
          <div className="flex items-center justify-end px-6 py-4 border-t border-tea/20 gap-2">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}
