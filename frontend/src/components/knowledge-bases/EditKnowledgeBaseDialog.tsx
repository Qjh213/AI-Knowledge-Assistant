import { useState, type FormEvent } from 'react'
import { LoaderCircle, PencilLine, X } from 'lucide-react'

interface EditKnowledgeBaseDialogProps {
  open: boolean
  currentName: string
  isPending: boolean
  errorMessage?: string
  onClose: () => void
  onConfirm: (name: string) => void
}

export function EditKnowledgeBaseDialog({
  open,
  currentName,
  isPending,
  errorMessage,
  onClose,
  onConfirm,
}: EditKnowledgeBaseDialogProps) {
  const [name, setName] = useState(currentName)
  const [validationError, setValidationError] = useState<string | null>(null)

  if (!open) return null

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalizedName = name.trim()

    if (!normalizedName) {
      setValidationError('请输入知识库名称。')
      return
    }

    if (normalizedName.length > 100) {
      setValidationError('知识库名称不能超过 100 个字符。')
      return
    }

    setValidationError(null)
    onConfirm(normalizedName)
  }

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 px-4 py-8 backdrop-blur-sm"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !isPending) onClose()
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-knowledge-base-title"
        className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl shadow-slate-950/15"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="grid size-11 place-items-center rounded-xl bg-indigo-50 text-indigo-600">
            <PencilLine size={21} />
          </div>
          <button
            type="button"
            aria-label="关闭"
            disabled={isPending}
            onClick={onClose}
            className="rounded-xl p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50"
          >
            <X size={20} />
          </button>
        </div>

        <h2 id="edit-knowledge-base-title" className="mt-5 text-xl font-semibold text-slate-950">
          编辑知识库名称
        </h2>
        <form className="mt-5" onSubmit={handleSubmit}>
          <label htmlFor="knowledge-base-name" className="text-sm font-medium text-slate-700">
            名称
          </label>
          <input
            id="knowledge-base-name"
            autoFocus
            maxLength={100}
            disabled={isPending}
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="mt-2 h-11 w-full rounded-xl border border-slate-200 px-3.5 text-sm outline-none transition focus:border-indigo-400 focus:ring-4 focus:ring-indigo-50 disabled:bg-slate-50"
          />
          {(validationError || errorMessage) && (
            <p className="mt-3 rounded-xl bg-rose-50 px-3.5 py-3 text-sm text-rose-700">
              {validationError || errorMessage}
            </p>
          )}
          <div className="mt-6 flex justify-end gap-3 border-t border-slate-100 pt-5">
            <button type="button" disabled={isPending} onClick={onClose} className="h-10 rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50">
              取消
            </button>
            <button type="submit" disabled={isPending} className="inline-flex h-10 min-w-24 items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60">
              {isPending && <LoaderCircle size={17} className="animate-spin" />}
              {isPending ? '保存中' : '保存'}
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}
