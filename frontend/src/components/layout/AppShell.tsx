import {
  BookOpen,
  Database,
  Menu,
  MessageSquareText,
  X,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { getServiceConnection } from '../../api/health'

const navigation = [
  { label: '知识库', to: '/knowledge-bases', icon: Database },
  {
    label: '最近对话',
    to: '/conversations',
    icon: MessageSquareText,
  },
]

export function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const serviceQuery = useQuery({
    queryKey: ['service-connection'],
    queryFn: getServiceConnection,
    refetchInterval: 30_000,
    retry: false,
  })
  const connection = serviceQuery.data ?? {
    state: 'offline' as const,
    label: '正在检查服务…',
  }
  const statusColor = {
    healthy: 'bg-emerald-500',
    degraded: 'bg-amber-500',
    offline: 'bg-rose-500',
  }[connection.state]

  return (
    <div className="min-h-screen bg-[#f5f7fb] text-slate-900">
      {sidebarOpen && (
        <button
          className="fixed inset-0 z-30 bg-slate-950/30 lg:hidden"
          aria-label="关闭导航"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-slate-200 bg-white transition-transform duration-200 lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-20 items-center justify-between border-b border-slate-100 px-6">
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-xl bg-indigo-600 text-white shadow-sm shadow-indigo-200">
              <BookOpen size={21} strokeWidth={2.2} />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-900">AI 知识助手</p>
              <p className="text-xs text-slate-500">Knowledge workspace</p>
            </div>
          </div>
          <button
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 lg:hidden"
            aria-label="关闭导航"
            onClick={() => setSidebarOpen(false)}
          >
            <X size={20} />
          </button>
        </div>

        <nav className="flex-1 space-y-1 px-4 py-6">
          <p className="mb-3 px-3 text-xs font-semibold tracking-wider text-slate-400 uppercase">
            工作区
          </p>
          {navigation.map((item) => {
            const Icon = item.icon

            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-indigo-50 text-indigo-700'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  }`
                }
              >
                <Icon size={19} />
                <span>{item.label}</span>
              </NavLink>
            )
          })}
        </nav>

        <div className="border-t border-slate-100 p-4">
          <div className="flex items-center gap-2 px-3 py-2 text-xs text-slate-500">
            <span className={`size-2 rounded-full ${statusColor}`} />
            {connection.label}
          </div>
        </div>
      </aside>

      <div className="lg:pl-72">
        <header className="sticky top-0 z-20 flex h-16 items-center border-b border-slate-200/80 bg-white/90 px-4 backdrop-blur md:px-8 lg:hidden">
          <button
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100"
            aria-label="打开导航"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu size={22} />
          </button>
          <span className="ml-3 text-sm font-semibold">AI 知识助手</span>
        </header>

        <main className="mx-auto min-h-screen max-w-7xl px-5 py-8 md:px-10 md:py-12">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
