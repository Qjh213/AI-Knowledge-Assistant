import { AlertTriangle, LoaderCircle, X } from 'lucide-react'

interface DeleteConversationDialogProps {
  open: boolean
  conversationTitle: string
  isPending: boolean
  errorMessage?: string
  onClose: () => void
  onConfirm: () => void
}

export function DeleteConversationDialog({
  open,
  conversationTitle,
  isPending,
  errorMessage,
  onClose,
  onConfirm,
}: DeleteConversationDialogProps) {
  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 px-4 py-8 backdrop-blur-sm"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !isPending) onClose()
      }}
    >
      <section role="alertdialog" aria-modal="true" aria-labelledby="delete-conversation-title" className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl shadow-slate-950/15">
        <div className="flex items-start justify-between gap-4">
          <div className="grid size-11 place-items-center rounded-xl bg-rose-50 text-rose-600">
            <AlertTriangle size={21} />
          </div>
          <button type="button" aria-label="关闭" disabled={isPending} onClick={onClose} className="rounded-xl p-2 text-slate-400 hover:bg-slate-100 disabled:opacity-50">
            <X size={20} />
          </button>
        </div>
        <h2 id="delete-conversation-title" className="mt-5 text-xl font-semibold text-slate-950">
          删除会话？
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          将永久删除“{conversationTitle}”及其中的全部消息。此操作无法撤销。
        </p>
        {errorMessage && <p className="mt-4 rounded-xl bg-rose-50 px-3.5 py-3 text-sm text-rose-700">{errorMessage}</p>}
        <div className="mt-6 flex justify-end gap-3 border-t border-slate-100 pt-5">
          <button type="button" disabled={isPending} onClick={onClose} className="h-10 rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50">取消</button>
          <button type="button" disabled={isPending} onClick={onConfirm} className="inline-flex h-10 min-w-28 items-center justify-center gap-2 rounded-xl bg-rose-600 px-4 text-sm font-semibold text-white hover:bg-rose-700 disabled:opacity-60">
            {isPending && <LoaderCircle size={17} className="animate-spin" />}
            {isPending ? '删除中' : '确认删除'}
          </button>
        </div>
      </section>
    </div>
  )
}
