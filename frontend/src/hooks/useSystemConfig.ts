import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import type { SystemConfig } from '../types'

let cachedConfig: SystemConfig | null = null
let loadPromise: Promise<SystemConfig> | null = null

export function useSystemConfig() {
  const [config, setConfig] = useState<SystemConfig | null>(cachedConfig)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    if (cachedConfig) {
      setConfig(cachedConfig)
      return
    }
    if (loadPromise) {
      const data = await loadPromise
      cachedConfig = data
      setConfig(data)
      return
    }
    loadPromise = (async () => {
      const data = await api.getSystemConfig()
      cachedConfig = data
      return data
    })()
    try {
      const data = await loadPromise
      setConfig(data)
    } catch {
      loadPromise = null
      cachedConfig = null
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const save = useCallback(async (patch: Partial<SystemConfig>) => {
    setSaving(true)
    try {
      const updated = await api.updateSystemConfig(patch)
      cachedConfig = updated
      setConfig(updated)
    } catch (e: any) {
      throw e
    } finally {
      setSaving(false)
    }
  }, [])

  const reload = useCallback(async () => {
    loadPromise = null
    cachedConfig = null
    await load()
  }, [load])

  return { config, saving, save, reload }
}
