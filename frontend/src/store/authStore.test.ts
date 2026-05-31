import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useAuthStore } from './authStore'
import { api } from '../api'

vi.mock('../api', () => ({
  api: {
    login: vi.fn(),
    register: vi.fn(),
    getMe: vi.fn(),
  },
}))

const mockUser = { id: '1', username: 'testuser', role: 'user' as const, is_active: true }
const mockLoginResponse = {
  access_token: 'test-token-123',
  token_type: 'bearer',
  user: mockUser,
}

describe('authStore', () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: null,
      token: null,
      isLoading: false,
      isInitialized: false,
    })
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('initial state has default values', () => {
    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
    expect(state.isLoading).toBe(false)
    expect(state.isInitialized).toBe(false)
  })

  it('login success updates user and token', async () => {
    vi.mocked(api.login).mockResolvedValueOnce(mockLoginResponse)

    await useAuthStore.getState().login('testuser', 'testpass')

    const state = useAuthStore.getState()
    expect(state.user).toEqual(mockUser)
    expect(state.token).toBe('test-token-123')
    expect(state.isLoading).toBe(false)
    expect(localStorage.getItem('auth_token')).toBe('test-token-123')
  })

  it('login failure resets isLoading and does not set user', async () => {
    vi.mocked(api.login).mockRejectedValueOnce(new Error('Invalid credentials'))

    await expect(useAuthStore.getState().login('testuser', 'wrong')).rejects.toThrow('Invalid credentials')

    const state = useAuthStore.getState()
    expect(state.isLoading).toBe(false)
    expect(state.user).toBeNull()
    expect(state.token).toBeNull()
    expect(localStorage.getItem('auth_token')).toBeNull()
  })

  it('register calls api.register then api.login and sets user', async () => {
    vi.mocked(api.register).mockResolvedValueOnce(mockUser)
    vi.mocked(api.login).mockResolvedValueOnce(mockLoginResponse)

    await useAuthStore.getState().register('newuser', 'newpass')

    expect(api.register).toHaveBeenCalledWith({ username: 'newuser', password: 'newpass' })
    expect(api.login).toHaveBeenCalledWith({ username: 'newuser', password: 'newpass' })

    const state = useAuthStore.getState()
    expect(state.user).toEqual(mockUser)
    expect(state.token).toBe('test-token-123')
    expect(state.isLoading).toBe(false)
  })

  it('register failure resets isLoading and does not set user', async () => {
    vi.mocked(api.register).mockRejectedValueOnce(new Error('Username taken'))

    await expect(useAuthStore.getState().register('existing', 'pass')).rejects.toThrow('Username taken')

    const state = useAuthStore.getState()
    expect(state.isLoading).toBe(false)
    expect(state.user).toBeNull()
    expect(state.token).toBeNull()
  })

  it('logout clears localStorage and resets state', () => {
    useAuthStore.setState({ user: mockUser, token: 'some-token' })
    localStorage.setItem('auth_token', 'some-token')

    useAuthStore.getState().logout()

    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
    expect(state.token).toBeNull()
    expect(localStorage.getItem('auth_token')).toBeNull()
  })

  it('checkAuth with no token sets isInitialized', async () => {
    await useAuthStore.getState().checkAuth()

    const state = useAuthStore.getState()
    expect(state.isInitialized).toBe(true)
    expect(state.user).toBeNull()
    expect(state.token).toBeNull()
    expect(api.getMe).not.toHaveBeenCalled()
  })

  it('checkAuth with valid token calls getMe and sets user', async () => {
    localStorage.setItem('auth_token', 'valid-token')
    vi.mocked(api.getMe).mockResolvedValueOnce(mockUser)

    await useAuthStore.getState().checkAuth()

    const state = useAuthStore.getState()
    expect(state.user).toEqual(mockUser)
    expect(state.token).toBe('valid-token')
    expect(state.isInitialized).toBe(true)
  })

  it('checkAuth with invalid token clears auth and sets isInitialized', async () => {
    localStorage.setItem('auth_token', 'expired-token')
    vi.mocked(api.getMe).mockRejectedValueOnce(new Error('Token expired'))

    await useAuthStore.getState().checkAuth()

    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
    expect(state.token).toBeNull()
    expect(state.isInitialized).toBe(true)
    expect(localStorage.getItem('auth_token')).toBeNull()
  })

  it('auth:unauthorized event triggers logout', () => {
    useAuthStore.setState({ user: mockUser, token: 'some-token' })
    localStorage.setItem('auth_token', 'some-token')

    window.dispatchEvent(new CustomEvent('auth:unauthorized'))

    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
    expect(state.token).toBeNull()
    expect(localStorage.getItem('auth_token')).toBeNull()
  })
})
