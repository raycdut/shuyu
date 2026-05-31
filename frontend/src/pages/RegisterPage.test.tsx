import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import RegisterPage from './RegisterPage'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual as any,
    useNavigate: () => mockNavigate,
  }
})

const mockRegister = vi.fn()
let mockIsLoading = false

vi.mock('../store/authStore', () => ({
  useAuthStore: Object.assign(
    vi.fn((selector?: any) => {
      const state = {
        user: null,
        token: null,
        isLoading: mockIsLoading,
        isInitialized: true,
        login: vi.fn(),
        register: mockRegister,
        logout: vi.fn(),
        checkAuth: vi.fn(),
      }
      return selector ? selector(state) : state
    }),
    { getState: vi.fn(() => ({ user: null, token: null })) }
  ),
}))

function renderRegisterPage() {
  return render(
    <MemoryRouter>
      <RegisterPage />
    </MemoryRouter>
  )
}

describe('RegisterPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockIsLoading = false
  })

  it('renders registration form with all inputs', () => {
    renderRegisterPage()
    expect(screen.getByText('数语')).toBeInTheDocument()
    expect(screen.getByText('创建新账号')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('请输入用户名')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('请输入密码')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('再次输入密码')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '注册' })).toBeInTheDocument()
    expect(screen.getByText('已有账号？')).toBeInTheDocument()
  })

  it('submits form with valid inputs and navigates to home', async () => {
    mockRegister.mockResolvedValue(undefined)
    renderRegisterPage()

    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('请输入用户名'), { target: { value: 'newuser' } })
      fireEvent.change(screen.getByPlaceholderText('请输入密码'), { target: { value: 'pass123' } })
      fireEvent.change(screen.getByPlaceholderText('再次输入密码'), { target: { value: 'pass123' } })
    })

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '注册' }))
    })

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith('newuser', 'pass123')
    })
    expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true })
  })

  it('shows error when passwords do not match', async () => {
    renderRegisterPage()

    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('请输入用户名'), { target: { value: 'user' } })
      fireEvent.change(screen.getByPlaceholderText('请输入密码'), { target: { value: 'pass123' } })
      fireEvent.change(screen.getByPlaceholderText('再次输入密码'), { target: { value: 'different' } })
    })

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '注册' }))
    })

    expect(screen.getByText('两次输入的密码不一致')).toBeInTheDocument()
    expect(mockRegister).not.toHaveBeenCalled()
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('shows error message when registration fails', async () => {
    mockRegister.mockRejectedValue(new Error('用户名已存在'))
    renderRegisterPage()

    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('请输入用户名'), { target: { value: 'existing' } })
      fireEvent.change(screen.getByPlaceholderText('请输入密码'), { target: { value: 'pass123' } })
      fireEvent.change(screen.getByPlaceholderText('再次输入密码'), { target: { value: 'pass123' } })
    })

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '注册' }))
    })

    expect(screen.getByText('用户名已存在')).toBeInTheDocument()
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('shows generic error message when registration fails without message', async () => {
    mockRegister.mockRejectedValue(new Error())
    renderRegisterPage()

    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('请输入用户名'), { target: { value: 'user' } })
      fireEvent.change(screen.getByPlaceholderText('请输入密码'), { target: { value: 'pass123' } })
      fireEvent.change(screen.getByPlaceholderText('再次输入密码'), { target: { value: 'pass123' } })
    })

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '注册' }))
    })

    expect(screen.getByText('注册失败')).toBeInTheDocument()
  })

  it('disables submit button and shows "注册中…" when isLoading is true', () => {
    mockIsLoading = true
    renderRegisterPage()
    expect(screen.getByRole('button', { name: '注册中…' })).toBeDisabled()
  })

  it('has a link to login page', () => {
    renderRegisterPage()
    const loginLink = screen.getByText('去登录')
    expect(loginLink).toBeInTheDocument()
    expect(loginLink.closest('a')).toHaveAttribute('href', '/login')
  })
})
