import { create } from 'zustand'

interface UIState {
  leftOpen: boolean
  error: string | null
  setLeftOpen: (open: boolean) => void
  setError: (error: string | null) => void
}

export const useUIStore = create<UIState>((set) => ({
  leftOpen: true,
  error: null,
  setLeftOpen: (leftOpen) => set({ leftOpen }),
  setError: (error) => set({ error }),
}))
