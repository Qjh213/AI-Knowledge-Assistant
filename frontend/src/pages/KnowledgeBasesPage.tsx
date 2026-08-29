import { ArrowRight, Database, FileText, Plus, Sparkles } from 'lucide-react'

const overview = [
  { label: '知识库', value: '0', icon: Database },
  { label: '已处理文档', value: '0', icon: FileText },
  { label: '活跃对话', value: '0', icon: Sparkles },
]

export function KnowledgeBasesPage() {
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

        <button className="inline-flex h-11 items-center justify-center gap-2 self-start rounded-xl bg-indigo-600 px-4 text-sm font-semibold text-white shadow-sm shadow-indigo-200 transition hover:bg-indigo-700 sm:self-auto">
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
          <button className="mt-6 inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-indigo-200 hover:text-indigo-700">
            了解工作流程
            <ArrowRight size={17} />
          </button>
        </div>
      </section>
    </div>
  )
}
