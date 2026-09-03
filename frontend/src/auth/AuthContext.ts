import { createContext, useContext } from 'react'

export interface AuthUser {
  id: string
  username: string
  role: 'admin' | 'user'
  must_change_password: boolean
  csrf_token: string
}
export interface AuthState {
  user: AuthUser | null
  loading: boolean
  error: string
  reload: () => Promise<void>
  signIn: (username: string, password: string) => Promise<void>
  signOut: () => Promise<void>
}
export const AuthContext = createContext<AuthState | null>(null)
export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('AuthProvider missing')
  return context
}
