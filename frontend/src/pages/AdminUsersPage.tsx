import { useState, type FormEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ShieldCheck, Users } from 'lucide-react'
import { apiRequest } from '../lib/apiClient'

interface Limits { storage_limit_mb: number; upload_limit_mb: number; processing_limit: number; daily_ai_limit: number }
interface Account extends Limits {
  id: string; username: string; role: string; is_active: boolean; must_change_password: boolean
  storage_used_bytes: number; ai_usage_count: number; knowledge_base_count: number; document_count: number; conversation_count: number
}
interface AuditEntry { id: string; actor: string; target: string; action: string; outcome: string; created_at: string; details: Record<string, unknown> }
interface Page<T> { items: T[]; total: number }
const labels: Record<string, string> = { create_user: '创建账号', enable_user: '启用账号', disable_user: '禁用账号', reset_password: '重置密码', update_limits: '调整额度', login: '登录', logout: '退出', change_password: '修改密码', reauthenticate: '身份确认', bootstrap_admin: '初始化管理员', bootstrap_admin_reset: '恢复管理员' }
const limitFields = [
  ['storage_limit_mb', '存储额度（MB）', 0, 1048576],
  ['upload_limit_mb', '单文件上限（MB）', 1, 100],
  ['processing_limit', '解析并发上限', 1, 16],
  ['daily_ai_limit', '每日 AI 请求次数', 0, 100000],
] as const
const inputClass = 'mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm'

export function AdminUsersPage() {
  const cache = useQueryClient()
  const [tab, setTab] = useState<'users' | 'audit'>('users')
  const [offset, setOffset] = useState(0)
  const [auditOffset, setAuditOffset] = useState(0)
  const [action, setAction] = useState<'create' | 'status' | 'password' | 'limits' | null>(null)
  const [target, setTarget] = useState<Account | null>(null)
  const [username, setUsername] = useState('')
  const [temporary, setTemporary] = useState('')
  const [adminPassword, setAdminPassword] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [limits, setLimits] = useState<Limits>({ storage_limit_mb: 1024, upload_limit_mb: 50, processing_limit: 2, daily_ai_limit: 100 })
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const accounts = useQuery({ queryKey: ['admin-users', offset], queryFn: () => apiRequest<Page<Account>>(`/admin/users?offset=${offset}&limit=20`), enabled: tab === 'users' })
  const audits = useQuery({ queryKey: ['admin-audit', auditOffset], queryFn: () => apiRequest<Page<AuditEntry>>(`/admin/audit-logs?offset=${auditOffset}&limit=20`), enabled: tab === 'audit' })
  const close = () => { setAction(null); setTarget(null); setTemporary(''); setAdminPassword(''); setConfirmed(false); setError('') }
  const open = (kind: NonNullable<typeof action>, account: Account | null = null) => {
    close(); setMessage(''); setUsername(''); setAction(kind); setTarget(account)
    if (account) setLimits({ storage_limit_mb: account.storage_limit_mb, upload_limit_mb: account.upload_limit_mb, processing_limit: account.processing_limit, daily_ai_limit: account.daily_ai_limit })
  }
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError(''); setMessage('')
    try {
      if (action === 'create') await apiRequest('/admin/users', { method: 'POST', body: JSON.stringify({ username, temporary_password: temporary }) })
      else if (target && action === 'limits') await apiRequest(`/admin/users/${target.id}/limits`, { method: 'PATCH', body: JSON.stringify(limits) })
      else if (target && confirmed && action === 'status') await apiRequest(`/admin/users/${target.id}/status`, { method: 'PATCH', body: JSON.stringify({ is_active: !target.is_active, admin_password: adminPassword }) })
      else if (target && confirmed && action === 'password') await apiRequest(`/admin/users/${target.id}/password`, { method: 'POST', body: JSON.stringify({ temporary_password: temporary, admin_password: adminPassword }) })
      else throw new Error('请确认操作。')
      close(); setMessage('操作已完成，已记录审计日志。')
      await Promise.all([cache.invalidateQueries({ queryKey: ['admin-users'] }), cache.invalidateQueries({ queryKey: ['admin-audit'] })])
    } catch (e) { setError(e instanceof Error ? e.message : '操作失败') }
    finally { setTemporary(''); setAdminPassword(''); setBusy(false) }
  }
  const queryError = tab === 'users' ? accounts.error : audits.error
  return <section>
    <header className="flex flex-wrap items-center justify-between gap-4">
      <div><p className="flex items-center gap-2 text-sm text-indigo-600"><ShieldCheck size={18} />管理员控制台</p><h1 className="mt-2 text-3xl font-semibold">账号与访问管理</h1></div>
      <button onClick={() => open('create')} className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-medium text-white">创建账号</button>
    </header>
    <p className="mt-4 text-sm leading-6 text-slate-500">仅管理普通账号和用量，不展示用户文档、对话正文或密码。管理员账号不能在此禁用、重置或更改角色。</p>
    <div className="my-6 flex gap-3 border-b border-slate-200 pb-3">
      <button aria-pressed={tab === 'users'} onClick={() => setTab('users')} className={`rounded-lg px-4 py-2 text-sm ${tab === 'users' ? 'bg-indigo-50 text-indigo-700' : 'text-slate-500'}`}>用户账号</button>
      <button aria-pressed={tab === 'audit'} onClick={() => setTab('audit')} className={`rounded-lg px-4 py-2 text-sm ${tab === 'audit' ? 'bg-indigo-50 text-indigo-700' : 'text-slate-500'}`}>操作日志</button>
    </div>
    {message && <p role="status" className="mb-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{message}</p>}
    {queryError && <p role="alert" className="mb-4 text-rose-600">加载失败：{queryError.message}<button className="ml-4 underline" onClick={() => void (tab === 'users' ? accounts.refetch() : audits.refetch())}>重试</button></p>}

    {action && <section aria-labelledby="account-action-title" className="mb-6 rounded-2xl border border-indigo-200 bg-white p-6 shadow-sm">
      <h2 id="account-action-title" className="text-lg font-semibold">{action === 'create' ? '创建普通用户' : `${action === 'limits' ? '配置额度' : action === 'password' ? '重置密码' : target?.is_active ? '禁用账号' : '启用账号'} · ${target?.username}`}</h2>
      <form onSubmit={submit} className="mt-4 space-y-4">
        <fieldset disabled={busy} className="grid gap-4 sm:grid-cols-2">
          {action === 'create' && <label className="text-sm">用户名<input required minLength={3} maxLength={32} pattern="[a-z0-9][a-z0-9_.\-]{2,31}" autoComplete="off" value={username} onChange={e => setUsername(e.target.value)} className={inputClass} /><span className="mt-1 block text-xs text-slate-500">3–32 位小写字母、数字或 ._-</span></label>}
          {(action === 'create' || action === 'password') && <label className="text-sm">临时密码<input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={temporary} onChange={e => setTemporary(e.target.value)} className={inputClass} /><span className="mt-1 block text-xs text-slate-500">至少 12 位；通过安全渠道交给用户，首次登录必须修改。</span></label>}
          {action === 'limits' && limitFields.map(([key, label, min, max]) => <label key={key} className="text-sm">{label}<input type="number" required min={min} max={max} step={1} value={limits[key]} onChange={e => setLimits({ ...limits, [key]: e.target.valueAsNumber })} className={inputClass} /></label>)}
          {(action === 'status' || action === 'password') && <>
            <label className="text-sm">你的管理员密码<input type="password" autoComplete="current-password" required maxLength={128} value={adminPassword} onChange={e => setAdminPassword(e.target.value)} className={inputClass} /></label>
            <label className="flex items-start gap-2 text-sm sm:col-span-2"><input type="checkbox" required checked={confirmed} onChange={e => setConfirmed(e.target.checked)} className="mt-1" />我确认对 {target?.username} 执行此操作。禁用或重置密码将撤销旧会话，保留用户数据。</label>
          </>}
        </fieldset>
        {action === 'limits' && <p className="text-xs leading-6 text-slate-500">每日请求按 UTC 零点重置，接受的检索、问答及解析任务计次（失败也计次），不是 token 或费用账单。额度调低不删除已有数据，也不中断已接受的任务；并发上限还受服务器总线程数限制。</p>}
        {error && <p role="alert" className="text-sm text-rose-600">{error}</p>}
        <div className="flex gap-3"><button disabled={busy} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white disabled:opacity-50">{busy ? '正在保存…' : '确认保存'}</button><button type="button" disabled={busy} onClick={close} className="rounded-lg border border-slate-300 px-4 py-2 text-sm">取消</button></div>
      </form>
    </section>}

    {tab === 'users' ? <>
      {accounts.isPending && <p className="p-6 text-slate-500">正在加载账号…</p>}
      <div className="grid gap-4 xl:grid-cols-2">{accounts.data?.items.map(account => <article key={account.id} className="rounded-2xl border border-slate-200 bg-white p-6">
        <div className="flex items-center justify-between gap-3"><h2 className="flex items-center gap-2 font-semibold"><Users size={18} className="text-slate-400" />{account.username}</h2><span className={`rounded-full px-3 py-1 text-xs ${account.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>{account.is_active ? '已启用' : '已禁用'}</span></div>
        <p className="mt-2 text-xs text-slate-500">{account.role === 'admin' ? '管理员 · 仅支持本人修改密码' : account.must_change_password ? '普通用户 · 待修改临时密码' : '普通用户'}</p>
        <dl className="mt-5 grid grid-cols-2 gap-4 text-sm"><div><dt className="text-slate-500">知识库 / 文档 / 对话</dt><dd className="mt-1 font-medium">{account.knowledge_base_count} / {account.document_count} / {account.conversation_count}</dd></div><div><dt className="text-slate-500">今日 AI 请求</dt><dd className="mt-1 font-medium">{account.ai_usage_count} / {account.daily_ai_limit}</dd></div><div><dt className="text-slate-500">已用存储 / 额度</dt><dd className="mt-1 font-medium">{(account.storage_used_bytes / 1048576).toFixed(1)} / {account.storage_limit_mb} MB</dd></div><div><dt className="text-slate-500">单文件 / 并发</dt><dd className="mt-1 font-medium">{account.upload_limit_mb} MB / {account.processing_limit}</dd></div></dl>
        {account.role === 'user' && <div className="mt-5 flex flex-wrap gap-4 border-t border-slate-100 pt-4 text-sm"><button onClick={() => open('limits', account)} className="text-indigo-600">配置额度</button><button onClick={() => open('password', account)} className="text-slate-600">重置密码</button><button onClick={() => open('status', account)} className={account.is_active ? 'text-rose-600' : 'text-emerald-600'}>{account.is_active ? '禁用账号' : '启用账号'}</button></div>}
      </article>)}</div>
      {accounts.data && <Pagination offset={offset} total={accounts.data.total} setOffset={setOffset} />}
    </> : <>
      {audits.isPending && <p className="p-6 text-slate-500">正在加载日志…</p>}
      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-slate-500"><tr>{['时间', '操作者', '目标账号', '操作', '结果'].map(label => <th key={label} className="whitespace-nowrap p-4 font-medium">{label}</th>)}</tr></thead><tbody>{audits.data?.items.map(log => <tr key={log.id} className="border-t border-slate-100"><td className="whitespace-nowrap p-4">{new Date(log.created_at).toLocaleString()}</td><td className="p-4">{log.actor}</td><td className="p-4">{log.target}</td><td className="p-4">{labels[log.action] ?? log.action}{Object.keys(log.details).length > 0 && <details className="mt-1 text-xs text-slate-500"><summary>额度变更详情</summary><pre className="mt-2 whitespace-pre-wrap">{JSON.stringify(log.details, null, 2)}</pre></details>}</td><td className="p-4">{log.outcome === 'success' ? '成功' : log.outcome === 'conflict' ? '冲突' : '拒绝'}</td></tr>)}</tbody></table>{audits.data?.total === 0 && <p className="p-6 text-slate-500">暂无操作日志。</p>}</div>
      {audits.data && <Pagination offset={auditOffset} total={audits.data.total} setOffset={setAuditOffset} />}
    </>}
  </section>
}

function Pagination({ offset, total, setOffset }: { offset: number; total: number; setOffset: (value: number) => void }) {
  return <div className="mt-5 flex items-center justify-end gap-4 text-sm text-slate-500"><span>共 {total} 条 · 第 {offset / 20 + 1} 页</span><button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))} className="disabled:opacity-30">上一页</button><button disabled={offset + 20 >= total} onClick={() => setOffset(offset + 20)} className="disabled:opacity-30">下一页</button></div>
}
