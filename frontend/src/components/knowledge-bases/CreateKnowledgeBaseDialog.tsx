import { useMutation, useQueryClient } from '@tanstack/react-query'
import { LoaderCircle, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { createKnowledgeBase } from '../../api/knowledgeBases'
import { useToast } from '../../lib/toast'

interface CreateKnowledgeBaseDialogProps {
  open: boolean
  onClose: () => void
}

export function CreateKnowledgeBaseDialog({
  open,
  onClose,
}: CreateKnowledgeBaseDialogProps) {
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)

  const createMutation = useMutation({
    mutationFn: createKnowledgeBase,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['knowledge-bases'] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] }),
      ])
      setName('')
      setDescription('')
      setValidationError(null)
      onClose()
      showToast('知识库创建成功。')
    },
    onError: (error) => {
      showToast(
        error instanceof Error ? error.message : '创建知识库失败。',
        'error',
      )
    },
  })

  if (!open) {
    return null
  }

  function handleClose() {
    if (!createMutation.isPending) {
      createMutation.reset()
      setValidationError(null)
      onClose()
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const normalizedName = name.trim()

    if (!normalizedName) {
      setValidationError('请输入知识库名称。')
      return
    }

    setValidationError(null)
    createMutation.mutate({
      name: normalizedName,
      description: description.trim() || null,
    })
  }

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 px-4 py-8 backdrop-blur-sm"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          handleClose()
        }
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-knowledge-base-title"
        className="w-full max-w-lg rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl shadow-slate-950/15 md:p-7"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2
              id="create-knowledge-base-title"
              className="text-xl font-semibold text-slate-950"
            >
              创建知识库
            </h2>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              创建后即可上传相关文档并开始知识问答。
            </p>
          </div>
          <button
            type="button"
            className="rounded-xl p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="关闭"
            disabled={createMutation.isPending}
            onClick={handleClose}
          >
            <X size={20} />
          </button>
        </div>

        <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">
              名称 <span className="text-rose-500">*</span>
            </span>
            <input
              autoFocus
              value={name}
              maxLength={100}
              disabled={createMutation.isPending}
              onChange={(event) => setName(event.target.value)}
              placeholder="例如：产品使用手册"
              className="mt-2 h-11 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100 disabled:bg-slate-50"
            />
            <span className="mt-1.5 block text-right text-xs text-slate-400">
              {name.length}/100
            </span>
          </label>

          <label className="block">
            <span className="text-sm font-medium text-slate-700">描述</span>
            <textarea
              value={description}
              maxLength={2000}
              rows={4}
              disabled={createMutation.isPending}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="简单说明这个知识库包含哪些资料（可选）"
              className="mt-2 w-full resize-none rounded-xl border border-slate-200 bg-white px-3.5 py-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100 disabled:bg-slate-50"
            />
            <span className="mt-1.5 block text-right text-xs text-slate-400">
              {description.length}/2000
            </span>
          </label>

          {(validationError || createMutation.isError) && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-3 text-sm text-rose-700">
              {validationError ??
                (createMutation.error instanceof Error
                  ? createMutation.error.message
                  : '创建知识库失败，请稍后重试。')}
            </div>
          )}

          <div className="flex justify-end gap-3 border-t border-slate-100 pt-5">
            <button
              type="button"
              disabled={createMutation.isPending}
              onClick={handleClose}
              className="h-10 rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="inline-flex h-10 min-w-28 items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {createMutation.isPending && (
                <LoaderCircle size={17} className="animate-spin" />
              )}
              {createMutation.isPending ? '创建中' : '创建'}
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}
