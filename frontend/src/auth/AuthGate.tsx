import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './AuthContext'

export function AuthGate({ adminOnly = false }: { adminOnly?: boolean }) {
  const { user, loading, error, reload } = useAuth()
  if (loading) return <p className="p-10 text-slate-500">正在验证登录状态…</p>
  if (error) return <div role="alert" className="p-10">{error}<button onClick={() => void reload()} className="ml-4 text-indigo-600">重试</button></div>
  if (!user) return <Navigate to="/login" replace />
  if (user.must_change_password) return <Navigate to="/change-password" replace />
  if (adminOnly && user.role !== 'admin') return <Navigate to="/knowledge-bases" replace />
  return <Outlet />
}
