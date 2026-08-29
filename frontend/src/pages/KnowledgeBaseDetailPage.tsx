import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  CalendarDays,
  Database,
  FileUp,
  MessageSquareText,
  RefreshCw,
  Trash2,
} from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  deleteKnowledgeBase,
  getKnowledgeBase,
} from '../api/knowledgeBases'
import { DeleteKnowledgeBaseDialog } from '../components/knowledge-bases/DeleteKnowledgeBaseDialog'

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

export function KnowledgeBaseDetailPage() {
  const { knowledgeBaseId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)

  const knowledgeBaseQuery = useQuery({
    queryKey: ['knowledge-base', knowledgeBaseId],
    queryFn: () => getKnowledgeBase(knowledgeBaseId!),
    enabled: Boolean(knowledgeBaseId),
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteKnowledgeBase(knowledgeBaseId!),
    onSuccess: async () => {
      queryClient.removeQueries({
        queryKey: ['knowledge-base', knowledgeBaseId],
      })
      await queryClient.invalidateQueries({ queryKey: ['knowledge-bases'] })
      navigate('/knowledge-bases', { replace: true })
    },
  })

  if (knowledgeBaseQuery.isPending) {
    return (
      <div className="animate-pulse">
        <div className="h-5 w-32 rounded bg-slate-200" />
        <div className="mt-8 h-10 w-2/3 rounded bg-slate-200" />
        <div className="mt-4 h-5 w-1/2 rounded bg-slate-200" />
        <div className="mt-10 h-56 rounded-3xl bg-white" />
      </div>
    )
  }

  if (knowledgeBaseQuery.isError || !knowledgeBaseQuery.data) {
    return (
      <div>
        <Link
          to="/knowledge-bases"
          className="inline-flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-indigo-600"
        >
          <ArrowLeft size={17} />
          返回知识库
        </Link>
        <section className="mt-8 rounded-2xl border border-rose-200 bg-rose-50 p-6">
          <h1 className="font-semibold text-rose-900">无法加载知识库</h1>
          <p className="mt-2 text-sm text-rose-700">
            {knowledgeBaseQuery.error instanceof Error
              ? knowledgeBaseQuery.error.message
              : '知识库不存在或服务暂时不可用。'}
          </p>
          <button
            onClick={() => void knowledgeBaseQuery.refetch()}
            className="mt-4 inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2 text-sm font-semibold text-rose-700 shadow-sm"
          >
            <RefreshCw size={16} />
            重新加载
          </button>
        </section>
      </div>
    )
  }

  const knowledgeBase = knowledgeBaseQuery.data

  return (
    <div>
      <Link
        to="/knowledge-bases"
        className="inline-flex items-center gap-2 text-sm font-medium text-slate-500 transition hover:text-indigo-600"
      >
        <ArrowLeft size={17} />
        返回知识库
      </Link>

      <div className="mt-7 flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
        <div className="flex min-w-0 items-start gap-4">
          <div className="grid size-14 shrink-0 place-items-center rounded-2xl bg-indigo-600 text-white shadow-sm shadow-indigo-200">
            <Database size={25} />
          </div>
          <div className="min-w-0">
            <h1 className="break-words text-3xl font-bold tracking-tight text-slate-950">
              {knowledgeBase.name}
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              {knowledgeBase.description || '这个知识库暂时没有描述。'}
            </p>
            <p className="mt-3 flex items-center gap-2 text-xs text-slate-400">
              <CalendarDays size={15} />
              创建于 {formatDateTime(knowledgeBase.created_at)}
            </p>
          </div>
        </div>

        <button
          onClick={() => {
            deleteMutation.reset()
            setDeleteDialogOpen(true)
          }}
          className="inline-flex h-10 items-center justify-center gap-2 self-start rounded-xl border border-rose-200 bg-white px-4 text-sm font-semibold text-rose-600 transition hover:bg-rose-50"
        >
          <Trash2 size={17} />
          删除知识库
        </button>
      </div>

      <section className="mt-10 grid gap-5 lg:grid-cols-2">
        <article className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm shadow-slate-200/40">
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-xl bg-sky-50 text-sky-600">
              <FileUp size={20} />
            </div>
            <div>
              <h2 className="font-semibold text-slate-950">知识文档</h2>
              <p className="text-xs text-slate-500">上传、处理并管理资料</p>
            </div>
          </div>
          <p className="mt-6 text-sm leading-6 text-slate-500">
            下一步将在这里接入文档列表、上传进度、处理状态和失败重试。
          </p>
          <button className="mt-6 inline-flex h-10 items-center gap-2 rounded-xl bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-800">
            <FileUp size={17} />
            上传文档
          </button>
        </article>

        <article className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm shadow-slate-200/40">
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-xl bg-violet-50 text-violet-600">
              <MessageSquareText size={20} />
            </div>
            <div>
              <h2 className="font-semibold text-slate-950">知识对话</h2>
              <p className="text-xs text-slate-500">基于文档进行连续问答</p>
            </div>
          </div>
          <p className="mt-6 text-sm leading-6 text-slate-500">
            文档处理完成后，可以创建会话，让助手结合历史消息和引用来源回答问题。
          </p>
          <button className="mt-6 inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-700 hover:border-indigo-200 hover:text-indigo-700">
            <MessageSquareText size={17} />
            开始对话
          </button>
        </article>
      </section>

      <DeleteKnowledgeBaseDialog
        open={deleteDialogOpen}
        knowledgeBaseName={knowledgeBase.name}
        isPending={deleteMutation.isPending}
        errorMessage={
          deleteMutation.isError
            ? deleteMutation.error instanceof Error
              ? deleteMutation.error.message
              : '删除失败，请稍后重试。'
            : undefined
        }
        onClose={() => {
          if (!deleteMutation.isPending) {
            setDeleteDialogOpen(false)
          }
        }}
        onConfirm={() => deleteMutation.mutate()}
      />
    </div>
  )
}
