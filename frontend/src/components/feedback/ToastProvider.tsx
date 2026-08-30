import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react'
import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react'
import { ToastContext, type ToastType } from '../../lib/toast'


interface ToastProviderProps {
  children: ReactNode
}

interface ToastItem {
  id: number
  message: string
  type: ToastType
}

const toastMeta = {
  success: {
    icon: CheckCircle2,
    className: 'border-emerald-200 text-emerald-700',
  },
  error: {
    icon: AlertCircle,
    className: 'border-rose-200 text-rose-700',
  },
  info: {
    icon: Info,
    className: 'border-sky-200 text-sky-700',
  },
} satisfies Record<ToastType, { icon: typeof Info; className: string }>

export function ToastProvider({ children }: ToastProviderProps) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const nextId = useRef(0)

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const showToast = useCallback((message: string, type: ToastType = 'success') => {
    const id = ++nextId.current
    setToasts((current) => [...current, { id, message, type }])
    window.setTimeout(() => dismiss(id), 4_000)
  }, [dismiss])

  const value = useMemo(() => ({ showToast }), [showToast])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed top-4 right-4 z-[100] flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2"
        aria-live="polite"
        aria-atomic="false"
      >
        {toasts.map((toast) => {
          const meta = toastMeta[toast.type]
          const Icon = meta.icon

          return (
            <div
              key={toast.id}
              role={toast.type === 'error' ? 'alert' : 'status'}
              className={`pointer-events-auto flex items-start gap-3 rounded-2xl border bg-white p-4 shadow-xl shadow-slate-900/10 ${meta.className}`}
            >
              <Icon size={19} className="mt-0.5 shrink-0" />
              <p className="flex-1 text-sm leading-5 text-slate-700">
                {toast.message}
              </p>
              <button
                type="button"
                aria-label="关闭提示"
                onClick={() => dismiss(toast.id)}
                className="rounded-md p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X size={16} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}
