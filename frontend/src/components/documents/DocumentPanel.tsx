import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  FileText,
  FileUp,
  LoaderCircle,
  Play,
  RefreshCw,
  Trash2,
} from 'lucide-react'
import {
  deleteDocument,
  getDocuments,
  processDocument,
  uploadDocument,
} from '../../api/documents'
import type { DocumentStatus } from '../../types/document'

interface DocumentPanelProps {
  knowledgeBaseId: string
}

const statusMeta: Record<
  DocumentStatus,
  { label: string; className: string; icon: typeof Clock3 }
> = {
  pending: {
    label: '等待处理',
    className: 'bg-amber-50 text-amber-700',
    icon: Clock3,
  },
  processing: {
    label: '处理中',
    className: 'bg-sky-50 text-sky-700',
    icon: LoaderCircle,
  },
  completed: {
    label: '处理完成',
    className: 'bg-emerald-50 text-emerald-700',
    icon: CheckCircle2,
  },
  failed: {
    label: '处理失败',
    className: 'bg-rose-50 text-rose-700',
    icon: AlertCircle,
  },
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

export function DocumentPanel({ knowledgeBaseId }: DocumentPanelProps) {
  const queryClient = useQueryClient()
  const queryKey = ['documents', knowledgeBaseId]

  const documentsQuery = useQuery({
    queryKey,
    queryFn: () => getDocuments(knowledgeBaseId),
    refetchInterval: (query) =>
      query.state.data?.items.some((item) => item.status === 'processing')
        ? 2_000
        : false,
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadDocument(knowledgeBaseId, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  })

  const processMutation = useMutation({
    mutationFn: (documentId: string) =>
      processDocument(knowledgeBaseId, documentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  })

  const deleteMutation = useMutation({
    mutationFn: (documentId: string) =>
      deleteDocument(knowledgeBaseId, documentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  })

  const mutationError =
    uploadMutation.error ?? processMutation.error ?? deleteMutation.error

  return (
    <section className="mt-10 rounded-3xl border border-slate-200 bg-white shadow-sm shadow-slate-200/40">
      <div className="flex flex-col gap-4 border-b border-slate-100 p-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-xl bg-sky-50 text-sky-600">
            <FileText size={20} />
          </div>
          <div>
            <h2 className="font-semibold text-slate-950">知识文档</h2>
            <p className="text-xs text-slate-500">
              {documentsQuery.data?.total ?? 0} 个文档
            </p>
          </div>
        </div>

        <label className="inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 text-sm font-semibold text-white transition hover:bg-slate-800 has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-60">
          {uploadMutation.isPending ? (
            <LoaderCircle size={17} className="animate-spin" />
          ) : (
            <FileUp size={17} />
          )}
          {uploadMutation.isPending ? '上传中' : '上传文档'}
          <input
            type="file"
            className="sr-only"
            accept=".txt,.md,.pdf,.docx"
            disabled={uploadMutation.isPending}
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) uploadMutation.mutate(file)
              event.target.value = ''
            }}
          />
        </label>
      </div>

      {mutationError && (
        <div className="mx-6 mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {mutationError instanceof Error
            ? mutationError.message
            : '文档操作失败，请稍后重试。'}
        </div>
      )}

      {documentsQuery.isPending && (
        <div className="space-y-3 p-6">
          {[0, 1].map((item) => (
            <div key={item} className="h-20 animate-pulse rounded-2xl bg-slate-50" />
          ))}
        </div>
      )}

      {documentsQuery.isError && (
        <div className="p-6 text-center">
          <p className="text-sm text-rose-600">
            {documentsQuery.error instanceof Error
              ? documentsQuery.error.message
              : '无法加载文档。'}
          </p>
          <button
            onClick={() => void documentsQuery.refetch()}
            className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-indigo-600"
          >
            <RefreshCw size={16} />
            重新加载
          </button>
        </div>
      )}

      {documentsQuery.isSuccess && documentsQuery.data.items.length === 0 && (
        <div className="px-6 py-12 text-center">
          <FileText size={30} className="mx-auto text-slate-300" />
          <p className="mt-4 text-sm font-medium text-slate-700">还没有文档</p>
          <p className="mt-1 text-xs text-slate-400">
            支持 TXT、Markdown、PDF 和 DOCX，单个文件最大 20 MB。
          </p>
        </div>
      )}

      {documentsQuery.isSuccess && documentsQuery.data.items.length > 0 && (
        <div className="divide-y divide-slate-100">
          {documentsQuery.data.items.map((document) => {
            const meta = statusMeta[document.status]
            const StatusIcon = meta.icon
            const isProcessingThis =
              processMutation.isPending &&
              processMutation.variables === document.id
            const isDeletingThis =
              deleteMutation.isPending && deleteMutation.variables === document.id

            return (
              <div
                key={document.id}
                className="flex flex-col gap-4 px-6 py-5 md:flex-row md:items-center"
              >
                <div className="grid size-11 shrink-0 place-items-center rounded-xl bg-slate-50 text-slate-500">
                  <FileText size={20} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-slate-900">
                    {document.original_filename}
                  </p>
                  <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                    <span>{formatBytes(document.file_size)}</span>
                    <span>·</span>
                    <span>{document.chunk_count} 个分块</span>
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-1 font-medium ${meta.className}`}
                    >
                      <StatusIcon
                        size={13}
                        className={document.status === 'processing' ? 'animate-spin' : ''}
                      />
                      {meta.label}
                    </span>
                  </div>
                  {document.error_message && (
                    <p className="mt-2 text-xs text-rose-600">
                      {document.error_message}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2 md:justify-end">
                  {(document.status === 'pending' || document.status === 'failed') && (
                    <button
                      disabled={processMutation.isPending || deleteMutation.isPending}
                      onClick={() => processMutation.mutate(document.id)}
                      className="inline-flex h-9 items-center gap-2 rounded-xl bg-indigo-50 px-3 text-xs font-semibold text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
                    >
                      {isProcessingThis ? (
                        <LoaderCircle size={15} className="animate-spin" />
                      ) : (
                        <Play size={15} />
                      )}
                      {isProcessingThis ? '处理中' : '开始处理'}
                    </button>
                  )}
                  <button
                    aria-label={`删除 ${document.original_filename}`}
                    disabled={processMutation.isPending || deleteMutation.isPending}
                    onClick={() => {
                      if (window.confirm(`确定删除“${document.original_filename}”吗？`)) {
                        deleteMutation.mutate(document.id)
                      }
                    }}
                    className="grid size-9 place-items-center rounded-xl text-slate-400 hover:bg-rose-50 hover:text-rose-600 disabled:opacity-50"
                  >
                    {isDeletingThis ? (
                      <LoaderCircle size={16} className="animate-spin" />
                    ) : (
                      <Trash2 size={16} />
                    )}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
