import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { BookOpen, ShieldCheck } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'

export function LoginPage() {
  const { user, loading, signIn } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  if (loading) return <p className="p-10">正在验证登录状态…</p>
  if (user) return <Navigate to={user.must_change_password ? '/change-password' : '/knowledge-bases'} replace />
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError('')
    try { await signIn(username, password) } catch (e) { setError(e instanceof Error ? e.message : '登录失败') }
    finally { setPassword(''); setBusy(false) }
  }
  return <main className="grid min-h-screen place-items-center bg-slate-50 p-6">
    <section className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
      <BookOpen className="mb-6 text-indigo-600" size={36} />
      <h1 className="text-2xl font-semibold">登录 AI 知识助手</h1>
      <p className="mt-3 text-sm leading-6 text-slate-500">进入你的独立知识空间。账号由管理员创建，暂不开放自助注册。</p>
      <form onSubmit={submit} className="mt-8 space-y-5">
        <label className="block text-sm font-medium">用户名<input autoComplete="username" required maxLength={32} value={username} onChange={e => setUsername(e.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 p-3" /></label>
        <label className="block text-sm font-medium">密码<input type="password" autoComplete="current-password" required maxLength={128} value={password} onChange={e => setPassword(e.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 p-3" /></label>
        {error && <p role="alert" className="text-sm text-rose-600">{error}</p>}
        <button disabled={busy} className="w-full rounded-xl bg-indigo-600 p-3 font-medium text-white disabled:opacity-50">{busy ? '正在登录…' : '登录'}</button>
      </form>
      <p className="mt-6 flex items-center gap-2 text-xs text-slate-500"><ShieldCheck size={16} />忘记密码请联系管理员重置。</p>
    </section>
  </main>
}
