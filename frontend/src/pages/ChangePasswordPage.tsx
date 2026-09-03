import { useState, type FormEvent } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { apiRequest } from '../lib/apiClient'

export function ChangePasswordPage() {
  const { user, loading, reload } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  if (loading) return <p className="p-10">正在验证登录状态…</p>
  if (!user) return <Navigate to="/login" replace />
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setError('')
    if (next !== confirm) { setError('两次新密码不一致。'); return }
    setBusy(true)
    try {
      await apiRequest('/auth/password', { method: 'POST', body: JSON.stringify({ current_password: current, new_password: next }) })
      await reload()
    } catch (e) { setError(e instanceof Error ? e.message : '修改失败') }
    finally { setCurrent(''); setNext(''); setConfirm(''); setBusy(false) }
  }
  return <main className="grid min-h-screen place-items-center bg-slate-50 p-6"><section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8">
    <h1 className="text-2xl font-semibold">修改密码</h1>
    <p className="mt-3 text-sm text-slate-500">{user.must_change_password ? '为保护账号，请先更换管理员设置的临时密码。' : '修改后，所有设备需要重新登录。'}新密码至少 12 个字符。</p>
    <form onSubmit={submit} className="mt-6 space-y-4">
      <label className="block text-sm">当前密码<input type="password" autoComplete="current-password" required maxLength={128} value={current} onChange={e => setCurrent(e.target.value)} className="mt-2 w-full rounded-lg border border-slate-300 p-3" /></label>
      <label className="block text-sm">新密码<input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={next} onChange={e => setNext(e.target.value)} className="mt-2 w-full rounded-lg border border-slate-300 p-3" /></label>
      <label className="block text-sm">确认新密码<input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={confirm} onChange={e => setConfirm(e.target.value)} className="mt-2 w-full rounded-lg border border-slate-300 p-3" /></label>
      {error && <p role="alert" className="text-sm text-rose-600">{error}</p>}
      <button disabled={busy} className="w-full rounded-lg bg-indigo-600 p-3 text-white disabled:opacity-50">{busy ? '正在修改…' : '修改并重新登录'}</button>
    </form>
    {!user.must_change_password && <Link to="/knowledge-bases" className="mt-4 block text-sm text-indigo-600">返回工作区</Link>}
  </section></main>
}
