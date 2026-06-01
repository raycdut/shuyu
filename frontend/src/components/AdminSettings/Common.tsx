import React from 'react'
import { useTranslation } from 'react-i18next'

interface SettingSectionProps {
  title: string
  children: React.ReactNode
  compact?: boolean
}

export function SettingSection({ title, children, compact }: SettingSectionProps) {
  return (
    <div className={compact ? 'mb-3 w-full' : 'mb-6 w-full'}>
      <label className={`block text-xs text-ink-lighter font-kai tracking-wide ${compact ? 'mb-1' : 'mb-2'}`}>{title}</label>
      <div className="w-full">
        {children}
      </div>
    </div>
  )
}

interface ToggleRowProps {
  label: string
  checked: boolean
  onChange: (v: boolean) => void
}

export function ToggleRow({ label, checked, onChange }: ToggleRowProps) {
  return (
    <div 
      className="flex items-center justify-between p-3 rounded-sm hover:bg-smoke/50 transition-colors cursor-pointer border border-transparent hover:border-tea/30"
      onClick={() => onChange(!checked)}
    >
      <span className="text-sm text-ink font-kai">{label}</span>
      <button
        className={`w-10 h-5 flex items-center rounded-full p-1 transition-colors duration-200 ${
          checked ? 'bg-celadon' : 'bg-tea/30'
        }`}
      >
        <div className={`bg-white w-3 h-3 rounded-full shadow-sm transition-transform duration-200 ${checked ? 'translate-x-5' : 'translate-x-0'}`} />
      </button>
    </div>
  )
}

interface PageHeaderProps {
  title: string
  subtitle?: string
  actions?: React.ReactNode
}

export function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  return (
    <div className="flex items-center justify-between mb-8 border-b border-tea pb-4">
      <div>
        <h3 className="text-xl font-song font-bold text-ink">{title}</h3>
        {subtitle && <p className="text-xs text-ink-lighter font-kai mt-1">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-3">{actions}</div>}
    </div>
  )
}

interface LoadingStateProps {
  message?: string
}

export function LoadingState({ message }: LoadingStateProps) {
  const { t } = useTranslation()
  return <div className="py-12 text-center text-ink-lighter font-kai">{message || t('common.loading')}</div>
}

interface EmptyStateProps {
  message?: string
  action?: React.ReactNode
  icon?: React.ReactNode
}

export function EmptyState({ message, action, icon }: EmptyStateProps) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col items-center justify-center py-16 border-2 border-dashed border-tea/30 rounded-lg bg-smoke/20">
      {icon && <div className="mb-3">{icon}</div>}
      <p className="text-sm text-ink-lighter font-kai mb-1">{message || t('common.noData')}</p>
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
