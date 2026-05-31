import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import LoginPage from './LoginPage'

const STORAGE_KEY_USERNAME = 'remembered_username'
const STORAGE_KEY_PASSWORD = 'remembered_password'
const STORAGE_KEY_REMEMBER = 'remember_me'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual as any,
    useNavigate: () => mockNavigate,
  }
})

const mockLogin = vi.fn()
let mockAuthUser: any = null
let mockIsLoading = false

const mockAuthState = () => ({
  user: mockAuthUser,
  token: null,
  isLoading: mockIsLoading,
  isInitialized: true,
  login: mockLogin,
  register: vi.fn(),
  logout: vi.fn(),
  checkAuth: vi.fn(),
})

vi.mock('../store/authStore', () => ({
  useAuthStore: Object.assign(
    vi.fn((selector?: any) => {
      const state = mockAuthState()
      return selector ? selector(state) : state
    }),
    { getState: vi.fn(() => mockAuthState()) }
  ),
}))

function renderLoginPage() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>
  )
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAuthUser = null
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('renders login form with title and inputs', () => {
    renderLoginPage()
    expect(screen.getByText('数语')).toBeInTheDocument()
    expect(screen.getByText('问你的数据')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('请输入用户名')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('请输入密码')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '登录' })).toBeInTheDocument()
    expect(screen.getByText('去注册')).toBeInTheDocument()
  })

  it('shows "记住我" checkbox unchecked by default', () => {
    renderLoginPage()
    const checkbox = screen.getByRole('checkbox')
    expect(checkbox).toBeInTheDocument()
    expect(checkbox).not.toBeChecked()
    expect(screen.getByText('记住我')).toBeInTheDocument()
  })

  it('auto-fills credentials and auto-logs in when "记住我" was enabled', async () => {
    localStorage.setItem(STORAGE_KEY_REMEMBER, 'true')
    localStorage.setItem(STORAGE_KEY_USERNAME, 'testuser')
    localStorage.setItem(STORAGE_KEY_PASSWORD, 'testpass')
    mockLogin.mockResolvedValue(undefined)

    renderLoginPage()

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('testuser', 'testpass')
    })

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true })
    })
  })

  it('shows "正在自动登录" during auto-login', async () => {
    localStorage.setItem(STORAGE_KEY_REMEMBER, 'true')
    localStorage.setItem(STORAGE_KEY_USERNAME, 'testuser')
    localStorage.setItem(STORAGE_KEY_PASSWORD, 'testpass')
    mockLogin.mockImplementation(() => new Promise(() => {}))

    renderLoginPage()

    expect(screen.getByText('正在自动登录…')).toBeInTheDocument()
  })

  it('falls back to form when auto-login fails', async () => {
    localStorage.setItem(STORAGE_KEY_REMEMBER, 'true')
    localStorage.setItem(STORAGE_KEY_USERNAME, 'testuser')
    localStorage.setItem(STORAGE_KEY_PASSWORD, 'testpass')
    mockLogin.mockRejectedValue(new Error('密码错误'))

    renderLoginPage()

    await waitFor(() => {
      expect(screen.getByPlaceholderText('请输入用户名')).toHaveValue('testuser')
    })
    expect(screen.getByPlaceholderText('请输入密码')).toHaveValue('testpass')
    expect(screen.getByRole('checkbox')).toBeChecked()
    expect(screen.getByRole('button', { name: '登录' })).toBeInTheDocument()
  })

  it('saves credentials to localStorage on manual login with "记住我" checked', async () => {
    mockLogin.mockResolvedValue(undefined)
    renderLoginPage()

    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('请输入用户名'), { target: { value: 'myuser' } })
      fireEvent.change(screen.getByPlaceholderText('请输入密码'), { target: { value: 'mypass' } })
      fireEvent.click(screen.getByRole('checkbox'))
    })

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '登录' }))
    })

    await waitFor(() => {
      expect(localStorage.getItem(STORAGE_KEY_USERNAME)).toBe('myuser')
      expect(localStorage.getItem(STORAGE_KEY_PASSWORD)).toBe('mypass')
      expect(localStorage.getItem(STORAGE_KEY_REMEMBER)).toBe('true')
    })
    expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true })
  })

  it('clears credentials from localStorage on manual login without "记住我"', async () => {
    localStorage.setItem(STORAGE_KEY_USERNAME, 'olduser')
    localStorage.setItem(STORAGE_KEY_PASSWORD, 'oldpass')
    localStorage.setItem(STORAGE_KEY_REMEMBER, 'true')
    mockLogin.mockRejectedValue(new Error('auto-login fail'))

    renderLoginPage()

    await waitFor(() => {
      expect(screen.getByPlaceholderText('请输入用户名')).toHaveValue('olduser')
    })

    mockLogin.mockResolvedValue(undefined)
    await act(async () => {
      fireEvent.click(screen.getByRole('checkbox'))
      fireEvent.change(screen.getByPlaceholderText('请输入用户名'), { target: { value: 'newuser' } })
      fireEvent.change(screen.getByPlaceholderText('请输入密码'), { target: { value: 'newpass' } })
    })

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '登录' }))
    })

    await waitFor(() => {
      expect(localStorage.getItem(STORAGE_KEY_USERNAME)).toBeNull()
      expect(localStorage.getItem(STORAGE_KEY_PASSWORD)).toBeNull()
      expect(localStorage.getItem(STORAGE_KEY_REMEMBER)).toBeNull()
    })
    expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true })
  })

  it('shows error message on login failure', async () => {
    mockLogin.mockRejectedValue(new Error('用户名或密码错误'))
    renderLoginPage()

    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('请输入用户名'), { target: { value: 'baduser' } })
      fireEvent.change(screen.getByPlaceholderText('请输入密码'), { target: { value: 'badpass' } })
    })

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '登录' }))
    })

    expect(screen.getByText('用户名或密码错误')).toBeInTheDocument()
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('disables submit button and shows "登录中…" when isLoading is true', () => {
    mockIsLoading = true
    renderLoginPage()
    expect(screen.getByRole('button', { name: '登录中…' })).toBeDisabled()
  })

  it('does not auto-login when "记住我" was not enabled', () => {
    localStorage.setItem(STORAGE_KEY_USERNAME, 'testuser')
    localStorage.setItem(STORAGE_KEY_PASSWORD, 'testpass')

    renderLoginPage()

    expect(mockLogin).not.toHaveBeenCalled()
  })

  it('redirects to home if already logged in', () => {
    mockAuthUser = { id: '1', username: 'admin', role: 'admin' as const, is_active: true }

    renderLoginPage()

    expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true })
  })
})
