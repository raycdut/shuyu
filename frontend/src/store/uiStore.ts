import { create } from 'zustand'

interface UIState {
  leftOpen: boolean
  rightOpen: boolean
  error: string | null
  setLeftOpen: (open: boolean) => void
  setRightOpen: (open: boolean) => void
  setError: (error: string | null) => void
}

export const useUIStore = create<UIState>((set) => ({
  leftOpen: true,
  rightOpen: true,
  error: null,
  setLeftOpen: (leftOpen) => set({ leftOpen }),
  setRightOpen: (rightOpen) => set({ rightOpen }),
  setError: (error) => set({ error }),
}))
