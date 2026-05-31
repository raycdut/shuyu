import { describe, it, expect, vi, beforeEach } from 'vitest'
import { api } from './index'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function mockResponse(overrides: Partial<Response> = {}): Response {
  const defaults = {
    ok: true,
    status: 200,
    statusText: 'OK',
    headers: new Headers({ 'Content-Type': 'application/json' }),
    json: async () => ({}),
    text: async () => '',
  }
  return { ...defaults, ...overrides } as Response
}

describe('api', () => {
  beforeEach(() => {
    mockFetch.mockReset()
    localStorage.clear()
  })

  describe('login', () => {
    it('calls fetch with correct URL and headers', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse())

      await api.login({ username: 'testuser', password: 'testpass' })

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/auth/login',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    })

    it('sends proper JSON body', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse())

      await api.login({ username: 'alice', password: 'secret' })

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/auth/login',
        expect.objectContaining({
          body: JSON.stringify({ username: 'alice', password: 'secret' }),
        }),
      )
    })

    it('returns parsed response', async () => {
      const responseData = {
        access_token: 'token123',
        token_type: 'bearer',
        user: { id: '1', username: 'alice', role: 'user', is_active: true },
      }
      mockFetch.mockResolvedValueOnce(
        mockResponse({ json: async () => responseData }),
      )

      const result = await api.login({ username: 'alice', password: 'secret' })
      expect(result).toEqual(responseData)
    })

    it('throws on non-ok response', async () => {
      mockFetch.mockResolvedValueOnce(
        mockResponse({
          ok: false,
          status: 400,
          statusText: 'Bad Request',
          text: async () => 'Invalid credentials',
        }),
      )

      await expect(
        api.login({ username: 'alice', password: 'wrong' }),
      ).rejects.toThrow('HTTP 400: Invalid credentials')
    })
  })

  describe('sendMessage', () => {
    it('calls /chat endpoint with POST', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse())

      await api.sendMessage('Hello')

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/chat',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    })

    it('passes message, session_id, db_id, mode in body', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse())

      await api.sendMessage('Hi', 'sess-1', 'db-1', 'normal')

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/chat',
        expect.objectContaining({
          body: JSON.stringify({
            message: 'Hi',
            session_id: 'sess-1',
            db_id: 'db-1',
            mode: 'normal',
          }),
        }),
      )
    })

    it('sends null for optional params when not provided', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse())

      await api.sendMessage('Hello')

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/chat',
        expect.objectContaining({
          body: JSON.stringify({
            message: 'Hello',
            session_id: null,
            db_id: null,
            mode: 'fast',
          }),
        }),
      )
    })
  })

  describe('getSessions', () => {
    it('calls /sessions endpoint with GET', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse())

      await api.getSessions()

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/sessions',
        expect.objectContaining({
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    })

    it('includes auth token when available', async () => {
      localStorage.setItem('auth_token', 'my-token')
      mockFetch.mockResolvedValueOnce(mockResponse())

      await api.getSessions()

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/sessions',
        expect.objectContaining({
          headers: {
            'Content-Type': 'application/json',
            Authorization: 'Bearer my-token',
          },
        }),
      )
    })

    it('does not include auth header when token is missing', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse())

      await api.getSessions()

      const callArgs = mockFetch.mock.calls[0][1]
      expect(callArgs.headers).not.toHaveProperty('Authorization')
    })
  })

  describe('401 handling', () => {
    it('clears localStorage token on 401 response', async () => {
      localStorage.setItem('auth_token', 'bad-token')
      mockFetch.mockResolvedValueOnce(
        mockResponse({
          ok: false,
          status: 401,
          statusText: 'Unauthorized',
          text: async () => 'Unauthorized',
        }),
      )

      await expect(api.getMe()).rejects.toThrow()
      expect(localStorage.getItem('auth_token')).toBeNull()
    })

    it('dispatches auth:unauthorized custom event on 401', async () => {
      localStorage.setItem('auth_token', 'bad-token')
      mockFetch.mockResolvedValueOnce(
        mockResponse({
          ok: false,
          status: 401,
          statusText: 'Unauthorized',
          text: async () => 'Unauthorized',
        }),
      )

      const dispatchSpy = vi.spyOn(window, 'dispatchEvent')

      await expect(api.getMe()).rejects.toThrow()

      expect(dispatchSpy).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'auth:unauthorized' }),
      )
      dispatchSpy.mockRestore()
    })
  })
})
