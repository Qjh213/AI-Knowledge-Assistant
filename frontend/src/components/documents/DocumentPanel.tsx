import { useEffect, useMemo, useRef } from 'react'
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
  Sparkles,
  Trash2,
} from 'lucide-react'
import {
  deleteDocument,
  getDocuments,
  processDocument,
  processDocumentWithMinerU,
  refreshMinerUDocument,
  uploadDocument,
} from '../../api/documents'
import type { DocumentListResponse, DocumentStatus } from '../../types/document'
import { useToast } from '../../lib/toast'

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
  const { showToast } = useToast()
  const queryKey = useMemo(
    () => ['documents', knowledgeBaseId] as const,
    [knowledgeBaseId],
  )
  const refreshInFlight = useRef(false)

  const documentsQuery = useQuery({
    queryKey,
    queryFn: () => getDocuments(knowledgeBaseId),
  })

  useEffect(() => {
    const processingDocuments = documentsQuery.data?.items.filter(
      (item) => item.status === 'processing' && item.parser === 'mineru',
    )

    if (!processingDocuments?.length) return

    let cancelled = false
    const timeoutId = window.setTimeout(async () => {
      if (refreshInFlight.current) return
      refreshInFlight.current = true

      try {
        const refreshed = await Promise.allSettled(
          processingDocuments.map((item) =>
            refreshMinerUDocument(knowledgeBaseId, item.id),
          ),
        )
        if (cancelled) return

        const refreshedById = new Map(
          refreshed.flatMap((result, index) =>
            result.status === 'fulfilled'
              ? [[processingDocuments[index].id, result.value] as const]
              : [],
          ),
        )

        if (refreshedById.size > 0) {
          queryClient.setQueryData<DocumentListResponse>(queryKey, (current) =>
            current
              ? {
                  ...current,
                  items: current.items.map(
                    (item) => refreshedById.get(item.id) ?? item,
                  ),
                }
              : current,
          )
        }

        if (refreshed.some((result) => result.status === 'rejected')) {
          await queryClient.invalidateQueries({ queryKey })
        }
      } finally {
        refreshInFlight.current = false
      }
    }, 3_000)

    return () => {
      cancelled = true
      window.clearTimeout(timeoutId)
    }
  }, [documentsQuery.data, knowledgeBaseId, queryClient, queryKey])

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadDocument(knowledgeBaseId, file),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey })
      showToast('文档上传成功，请开始处理。')
    },
    onError: (error) =>
      showToast(error instanceof Error ? error.message : '文档上传失败。', 'error'),
  })

  const processMutation = useMutation({
    mutationFn: (documentId: string) =>
      processDocument(knowledgeBaseId, documentId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey }),
        queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] }),
      ])
      showToast('文档处理完成。')
    },
    onError: (error) =>
      showToast(error instanceof Error ? error.message : '文档处理失败。', 'error'),
  })

  const mineruMutation = useMutation({
    mutationFn: (documentId: string) =>
      processDocumentWithMinerU(knowledgeBaseId, documentId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey })
      showToast('文档已提交 MinerU，正在解析。')
    },
    onError: (error) =>
      showToast(
        error instanceof Error ? error.message : 'MinerU 任务提交失败。',
        'error',
      ),
  })

  const deleteMutation = useMutation({
    mutationFn: (documentId: string) =>
      deleteDocument(knowledgeBaseId, documentId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey }),
        queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] }),
      ])
      showToast('文档已删除。')
    },
    onError: (error) =>
      showToast(error instanceof Error ? error.message : '删除文档失败。', 'error'),
  })

  const mutationError =
    uploadMutation.error ??
    processMutation.error ??
    mineruMutation.error ??
    deleteMutation.error

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
            const isLocalProcessingThis =
              processMutation.isPending &&
              processMutation.variables === document.id
            const isMineruProcessingThis =
              mineruMutation.isPending &&
              mineruMutation.variables === document.id
            const isDeletingThis =
              deleteMutation.isPending && deleteMutation.variables === document.id
            const canUseMinerU = /\.(pdf|docx)$/i.test(document.original_filename)
            const operationsPending =
              processMutation.isPending ||
              mineruMutation.isPending ||
              deleteMutation.isPending

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
                  {document.parser === 'mineru' && (
                    <div className="mt-2 max-w-md">
                      <div className="mb-1 flex items-center justify-between text-[11px] text-slate-500">
                        <span>MinerU 解析</span>
                        <span>{document.processing_progress}%</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full bg-sky-500 transition-[width] duration-500"
                          style={{
                            width: `${Math.max(
                              0,
                              Math.min(100, document.processing_progress),
                            )}%`,
                          }}
                        />
                      </div>
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2 md:justify-end">
                  {(document.status === 'pending' || document.status === 'failed') && (
                    <>
                      <button
                        disabled={operationsPending}
                        onClick={() => processMutation.mutate(document.id)}
                        className="inline-flex h-9 items-center gap-2 rounded-xl bg-indigo-50 px-3 text-xs font-semibold text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
                      >
                        {isLocalProcessingThis ? (
                          <LoaderCircle size={15} className="animate-spin" />
                        ) : (
                          <Play size={15} />
                        )}
                        本地处理
                      </button>
                      {canUseMinerU && (
                        <button
                          disabled={operationsPending}
                          onClick={() => mineruMutation.mutate(document.id)}
                          className="inline-flex h-9 items-center gap-2 rounded-xl bg-sky-50 px-3 text-xs font-semibold text-sky-700 hover:bg-sky-100 disabled:opacity-50"
                        >
                          {isMineruProcessingThis ? (
                            <LoaderCircle size={15} className="animate-spin" />
                          ) : (
                            <Sparkles size={15} />
                          )}
                          MinerU 解析
                        </button>
                      )}
                    </>
                  )}
                  <button
                    aria-label={`删除 ${document.original_filename}`}
                    disabled={operationsPending}
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
