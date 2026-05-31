import { createContext, useContext } from 'react'
import type { SystemConfig } from '../../types'

interface AdminSettingsValue {
  config: SystemConfig
  saving: boolean
  save: (patch: Partial<SystemConfig>) => Promise<void>
  reload: () => Promise<void>
}

const AdminSettingsContext = createContext<AdminSettingsValue | null>(null)

export function useAdminSettings(): AdminSettingsValue {
  const ctx = useContext(AdminSettingsContext)
  if (!ctx) {
    throw new Error('useAdminSettings must be used within AdminSettingsProvider')
  }
  return ctx
}

export { AdminSettingsContext }
