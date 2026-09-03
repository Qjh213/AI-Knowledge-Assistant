import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { ApiError, apiRequest, setCsrfToken, setCurrentAccount } from '../lib/apiClient'
import { AuthContext, type AuthUser } from './AuthContext'

export function AuthProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient()
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const generation = useRef(0)
  const accept = useCallback((next: AuthUser | null) => {
    setCsrfToken(next?.csrf_token ?? '')
    setCurrentAccount(next?.id ?? '')
    client.clear() // Never retain another user's cached documents or messages.
    setUser(next)
  }, [client])
  const reload = useCallback(async () => {
    const current = ++generation.current
    setLoading(true)
    try {
      const next = await apiRequest<AuthUser>('/auth/me')
      if (current === generation.current) { accept(next); setError('') }
    } catch (e) {
      if (current === generation.current) {
        accept(null)
        setError(e instanceof ApiError && e.status === 401 ? '' : '无法连接认证服务，请重试。')
      }
    } finally { if (current === generation.current) setLoading(false) }
  }, [accept])
  useEffect(() => {
    const timer = window.setTimeout(() => { void reload() }, 0)
    const counter = generation
    const expire = () => { ++generation.current; accept(null); setLoading(false) }
    const requirePassword = () => { void reload() }
    window.addEventListener('auth-expired', expire)
    window.addEventListener('password-required', requirePassword)
    return () => {
      window.clearTimeout(timer)
      ++counter.current
      window.removeEventListener('auth-expired', expire)
      window.removeEventListener('password-required', requirePassword)
    }
  }, [accept, reload])
  const signIn = async (username: string, password: string) => {
    const current = ++generation.current
    const next = await apiRequest<AuthUser>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) })
    if (current === generation.current) { accept(next); setError(''); setLoading(false) }
  }
  const signOut = async () => {
    try { await apiRequest<void>('/auth/logout', { method: 'POST' }) }
    catch (e) { if (!(e instanceof ApiError && e.status === 401)) throw e }
    ++generation.current
    accept(null)
  }
  return <AuthContext.Provider value={{ user, loading, error, reload, signIn, signOut }}>{children}</AuthContext.Provider>
}
