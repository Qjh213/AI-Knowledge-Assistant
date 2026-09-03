import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from './AuthProvider'
import { AuthContext, type AuthState } from './AuthContext'
import { AuthGate } from './AuthGate'
import { LoginPage } from '../pages/LoginPage'
import { AdminUsersPage } from '../pages/AdminUsersPage'
import { setCsrfToken, setCurrentAccount } from '../lib/apiClient'

const authenticated = { id: 'u1', username: 'alice', role: 'user' as const, must_change_password: false, csrf_token: 'csrf-test' }
const account = { ...authenticated, is_active: true, storage_used_bytes: 0, storage_limit_mb: 100, upload_limit_mb: 10, processing_limit: 1, daily_ai_limit: 10, ai_usage_count: 0, knowledge_base_count: 0, document_count: 0, conversation_count: 0 }
function json(data: unknown, status = 200) { return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } }) }
afterEach(() => { vi.unstubAllGlobals(); setCsrfToken(''); setCurrentAccount('') })

describe('authentication boundary', () => {
  it('signs in with credentials, does not expose registration, and clears previous cached data', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(json({ detail: 'login' }, 401)).mockResolvedValue(json(authenticated))
    vi.stubGlobal('fetch', fetcher)
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    client.setQueryData(['private'], 'previous user data')
    render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/login']}><AuthProvider><Routes>
      <Route path="/login" element={<LoginPage />} /><Route path="/knowledge-bases" element={<p>工作区内容</p>} />
    </Routes></AuthProvider></MemoryRouter></QueryClientProvider>)
    await screen.findByRole('button', { name: '登录' })
    expect(screen.queryByRole('button', { name: '注册' })).not.toBeInTheDocument()
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('用户名'), 'alice')
    await user.type(screen.getByLabelText('密码'), 'a-long-password-123')
    await user.click(screen.getByRole('button', { name: '登录' }))
    expect(await screen.findByText('工作区内容')).toBeInTheDocument()
    expect(client.getQueryData(['private'])).toBeUndefined()
    const options = fetcher.mock.calls[1][1] as RequestInit
    expect(options.credentials).toBe('include')
    expect(new Headers(options.headers).get('X-Requested-With')).toBe('KnowledgeAssistant')
  })

  it('removes protected content on session expiry', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(authenticated)))
    const client = new QueryClient()
    render(<QueryClientProvider client={client}><MemoryRouter><AuthProvider><Routes>
      <Route element={<AuthGate />}><Route index element={<p>私有内容</p>} /></Route>
      <Route path="/login" element={<p>请重新登录</p>} />
    </Routes></AuthProvider></MemoryRouter></QueryClientProvider>)
    await screen.findByText('私有内容')
    act(() => { window.dispatchEvent(new Event('auth-expired')) })
    expect(await screen.findByText('请重新登录')).toBeInTheDocument()
    expect(screen.queryByText('私有内容')).not.toBeInTheDocument()
  })

  it.each([
    [{ ...authenticated, must_change_password: true }, '请修改密码'],
    [authenticated, '普通工作区'],
  ])('blocks administrator route for restricted sessions', (user, expected) => {
    const context: AuthState = { user, loading: false, error: '', reload: vi.fn(), signIn: vi.fn(), signOut: vi.fn() }
    render(<AuthContext.Provider value={context}><MemoryRouter initialEntries={['/admin']}><Routes>
      <Route element={<AuthGate adminOnly />}><Route path="/admin" element={<p>管理员秘密页面</p>} /></Route>
      <Route path="/change-password" element={<p>请修改密码</p>} /><Route path="/knowledge-bases" element={<p>普通工作区</p>} />
    </Routes></MemoryRouter></AuthContext.Provider>)
    expect(screen.getByText(expected)).toBeInTheDocument()
    expect(screen.queryByText('管理员秘密页面')).not.toBeInTheDocument()
  })
})

describe('account administration', () => {
  function renderAdmin() {
    const fetcher = vi.fn().mockImplementation((_url: string, options: RequestInit = {}) => Promise.resolve(json(options.method ? {} : { items: [account], total: 1 })))
    vi.stubGlobal('fetch', fetcher)
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><AdminUsersPage /></QueryClientProvider>)
    return fetcher
  }
  it('requires confirmation and administrator password for reset, clears secrets on cancel', async () => {
    const fetcher = renderAdmin()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: '重置密码' }))
    const password = screen.getByLabelText(/临时密码/)
    expect(password).toHaveAttribute('type', 'password')
    await user.type(password, 'temporary-password-123')
    await user.click(screen.getByRole('button', { name: '确认保存' }))
    expect(fetcher.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(0)
    await user.click(screen.getByRole('button', { name: '取消' }))
    await user.click(screen.getByRole('button', { name: '重置密码' }))
    expect(screen.getByLabelText(/临时密码/)).toHaveValue('')
    await user.type(screen.getByLabelText(/临时密码/), 'temporary-password-123')
    await user.type(screen.getByLabelText('你的管理员密码'), 'administrator-password-123')
    await user.click(screen.getByRole('checkbox'))
    await user.click(screen.getByRole('button', { name: '确认保存' }))
    await waitFor(() => expect(fetcher.mock.calls.some(call => call[0].endsWith('/admin/users/u1/password') && call[1].method === 'POST')).toBe(true))
    expect(await screen.findByRole('status')).toHaveTextContent('操作已完成')
    expect(screen.queryByLabelText('你的管理员密码')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '删除账号' })).not.toBeInTheDocument()
  })
})
