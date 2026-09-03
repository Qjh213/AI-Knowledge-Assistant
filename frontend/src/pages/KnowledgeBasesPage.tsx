import { useQuery } from '@tanstack/react-query'
import {
  ArrowRight,
  Database,
  FileText,
  Plus,
  RefreshCw,
  Sparkles,
} from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { getKnowledgeBases } from '../api/knowledgeBases'
import { getDashboardOverview } from '../api/dashboard'
import { CreateKnowledgeBaseDialog } from '../components/knowledge-bases/CreateKnowledgeBaseDialog'
import { KnowledgeBaseGuideDialog } from '../components/knowledge-bases/KnowledgeBaseGuideDialog'

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(new Date(value))
}

export function KnowledgeBasesPage() {
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [guideDialogOpen, setGuideDialogOpen] = useState(false)
  const knowledgeBasesQuery = useQuery({
    queryKey: ['knowledge-bases'],
    queryFn: () => getKnowledgeBases(),
  })
  const overviewQuery = useQuery({
    queryKey: ['dashboard-overview'],
    queryFn: getDashboardOverview,
  })

  const overviewData = overviewQuery.data
  const overview = [
    {
      label: '知识库',
      value: overviewData ? String(overviewData.knowledge_base_count) : '—',
      icon: Database,
    },
    {
      label: '已处理文档',
      value: overviewData
        ? String(overviewData.processed_document_count)
        : '—',
      icon: FileText,
    },
    {
      label: '对话总数',
      value: overviewData ? String(overviewData.conversation_count) : '—',
      icon: Sparkles,
    },
  ]

  return (
    <div>
      <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="mb-2 text-sm font-medium text-indigo-600">知识工作区</p>
          <h1 className="text-3xl font-bold tracking-tight text-slate-950 md:text-4xl">
            管理你的知识库
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-500 md:text-base">
            上传文档并建立可检索的知识空间，让 AI 基于你的资料进行可靠回答。
          </p>
        </div>

        <button
          onClick={() => setCreateDialogOpen(true)}
          className="inline-flex h-11 items-center justify-center gap-2 self-start rounded-xl bg-indigo-600 px-4 text-sm font-semibold text-white shadow-sm shadow-indigo-200 transition hover:bg-indigo-700 sm:self-auto"
        >
          <Plus size={18} />
          创建知识库
        </button>
      </div>

      <section className="mt-8 grid gap-4 sm:grid-cols-3">
        {overview.map((item) => {
          const Icon = item.icon
          return (
            <article
              key={item.label}
              className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/40"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-500">{item.label}</span>
                <span className="grid size-9 place-items-center rounded-xl bg-slate-50 text-slate-500">
                  <Icon size={18} />
                </span>
              </div>
              <p className="mt-4 text-3xl font-bold tracking-tight text-slate-950">
                {item.value}
              </p>
            </article>
          )
        })}
      </section>

      {knowledgeBasesQuery.isPending && (
        <section className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((item) => (
            <div
              key={item}
              className="h-44 animate-pulse rounded-2xl border border-slate-200 bg-white p-5"
            >
              <div className="h-5 w-2/3 rounded bg-slate-100" />
              <div className="mt-4 h-4 w-full rounded bg-slate-100" />
              <div className="mt-2 h-4 w-1/2 rounded bg-slate-100" />
            </div>
          ))}
        </section>
      )}

      {knowledgeBasesQuery.isError && (
        <section className="mt-8 rounded-2xl border border-rose-200 bg-rose-50 p-6">
          <h2 className="font-semibold text-rose-900">无法连接后端服务</h2>
          <p className="mt-2 text-sm leading-6 text-rose-700">
            {knowledgeBasesQuery.error instanceof Error
              ? knowledgeBasesQuery.error.message
              : '加载知识库时发生未知错误。'}
          </p>
          <button
            className="mt-4 inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2 text-sm font-semibold text-rose-700 shadow-sm"
            onClick={() => void knowledgeBasesQuery.refetch()}
          >
            <RefreshCw size={16} />
            重新加载
          </button>
        </section>
      )}

      {knowledgeBasesQuery.isSuccess &&
        knowledgeBasesQuery.data.items.length > 0 && (
          <section className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {knowledgeBasesQuery.data.items.map((knowledgeBase) => (
              <Link
                key={knowledgeBase.id}
                to={`/knowledge-bases/${knowledgeBase.id}`}
                className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/40 transition hover:-translate-y-0.5 hover:border-indigo-200 hover:shadow-md"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="grid size-11 shrink-0 place-items-center rounded-xl bg-indigo-50 text-indigo-600">
                    <Database size={21} />
                  </div>
                  <ArrowRight
                    size={18}
                    className="text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-indigo-500"
                  />
                </div>
                <h2 className="mt-5 line-clamp-1 font-semibold text-slate-950">
                  {knowledgeBase.name}
                </h2>
                <p className="mt-2 line-clamp-2 min-h-10 text-sm leading-5 text-slate-500">
                  {knowledgeBase.description || '暂无描述'}
                </p>
                <p className="mt-5 text-xs text-slate-400">
                  创建于 {formatDate(knowledgeBase.created_at)}
                </p>
              </Link>
            ))}
          </section>
        )}

      {knowledgeBasesQuery.isSuccess &&
        knowledgeBasesQuery.data.items.length === 0 && (
          <section className="mt-8 overflow-hidden rounded-3xl border border-dashed border-slate-300 bg-white">
            <div className="mx-auto flex max-w-xl flex-col items-center px-6 py-16 text-center md:py-20">
              <div className="grid size-16 place-items-center rounded-2xl bg-indigo-50 text-indigo-600">
                <Database size={28} />
              </div>
              <h2 className="mt-6 text-xl font-semibold text-slate-950">
                创建第一个知识库
              </h2>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                知识库用于组织相关文档。创建后，你可以上传资料、完成向量处理并开始连续对话。
              </p>
              <button onClick={() => setGuideDialogOpen(true)} className="mt-6 inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-indigo-200 hover:text-indigo-700">
                查看使用指南
                <ArrowRight size={17} />
              </button>
            </div>
          </section>
        )}

      <KnowledgeBaseGuideDialog
        open={guideDialogOpen}
        onClose={() => setGuideDialogOpen(false)}
        onCreate={() => {
          setGuideDialogOpen(false)
          setCreateDialogOpen(true)
        }}
      />
      <CreateKnowledgeBaseDialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
      />
    </div>
  )
}
