import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useUIStore } from './uiStore'

describe('uiStore', () => {
  beforeEach(() => {
    useUIStore.setState({
      leftOpen: true,
      error: null,
    })
  })

  it('initial state has default values', () => {
    const state = useUIStore.getState()
    expect(state.leftOpen).toBe(true)
    expect(state.error).toBeNull()
  })

  it('setLeftOpen toggles left panel state', () => {
    useUIStore.getState().setLeftOpen(false)
    expect(useUIStore.getState().leftOpen).toBe(false)

    useUIStore.getState().setLeftOpen(true)
    expect(useUIStore.getState().leftOpen).toBe(true)
  })

  it('setError sets and clears error', () => {
    useUIStore.getState().setError('Something went wrong')
    expect(useUIStore.getState().error).toBe('Something went wrong')

    useUIStore.getState().setError(null)
    expect(useUIStore.getState().error).toBeNull()
  })

  it('handles multiple state changes', () => {
    useUIStore.getState().setLeftOpen(false)
    useUIStore.getState().setError('Error occurred')

    const state = useUIStore.getState()
    expect(state.leftOpen).toBe(false)
    expect(state.error).toBe('Error occurred')
  })
})
