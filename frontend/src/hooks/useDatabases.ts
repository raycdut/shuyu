import { useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useConfigStore } from '../store/configStore'
import { useUIStore } from '../store/uiStore'

export function useDatabases() {
  const { t } = useTranslation()
  const setDatabases = useConfigStore(s => s.setDatabases)
  const setError = useUIStore(s => s.setError)

  const loadDatabases = useCallback(async () => {
    try {
      const data = await api.getDatabases()
      setDatabases(data.databases || [])
    } catch (err: any) {
      setError(`${t('chat.loadDbListFailed')} ${err.message || t('session.unknownError')}`)
    }
  }, [setDatabases, setError, t])

  return { loadDatabases }
}
