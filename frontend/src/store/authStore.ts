import { create } from 'zustand'
import type { UserInfo } from '../types'
import { api } from '../api'

interface AuthState {
  user: UserInfo | null
  token: string | null
  isLoading: boolean
  isInitialized: boolean

  login: (username: string, password: string) => Promise<void>
  register: (username: string, password: string) => Promise<void>
  logout: () => void
  checkAuth: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem('auth_token'),
  isLoading: false,
  isInitialized: false,

  login: async (username, password) => {
    set({ isLoading: true })
    try {
      const res = await api.login({ username, password })
      localStorage.setItem('auth_token', res.access_token)
      set({ user: res.user, token: res.access_token, isLoading: false })
    } catch (e) {
      set({ isLoading: false })
      throw e
    }
  },

  register: async (username, password) => {
    set({ isLoading: true })
    try {
      await api.register({ username, password })
      const res = await api.login({ username, password })
      localStorage.setItem('auth_token', res.access_token)
      set({ user: res.user, token: res.access_token, isLoading: false })
    } catch (e) {
      set({ isLoading: false })
      throw e
    }
  },

  logout: () => {
    localStorage.removeItem('auth_token')
    set({ user: null, token: null })
  },

  checkAuth: async () => {
    const token = localStorage.getItem('auth_token')
    if (!token) {
      set({ isInitialized: true })
      return
    }
    try {
      const user = await api.getMe()
      set({ user, token, isInitialized: true })
    } catch {
      localStorage.removeItem('auth_token')
      set({ user: null, token: null, isInitialized: true })
    }
  },
}))

window.addEventListener('auth:unauthorized', () => {
  useAuthStore.getState().logout()
})
