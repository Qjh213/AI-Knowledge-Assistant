import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Clock3, MessageSquareText, RefreshCw, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { deleteConversation, getRecentConversations } from '../api/conversations'
import { useToast } from '../lib/toast'

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

export function RecentConversationsPage() {
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const conversationsQuery = useQuery({
    queryKey: ['recent-conversations'],
    queryFn: () => getRecentConversations(),
  })
  const deleteMutation = useMutation({
    mutationFn: ({
      knowledgeBaseId,
      conversationId,
    }: {
      knowledgeBaseId: string
      conversationId: string
    }) => deleteConversation(knowledgeBaseId, conversationId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['recent-conversations'] })
      await queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] })
      showToast('会话已删除', 'success')
    },
    onError: (error) => {
      showToast(error.message, 'error')
    },
  })

  return (
    <div>
      <p className="mb-2 text-sm font-medium text-indigo-600">对话记录</p>
      <h1 className="text-3xl font-bold tracking-tight text-slate-950 md:text-4xl">
        最近对话
      </h1>
      <p className="mt-3 text-sm leading-6 text-slate-500 md:text-base">
        继续你在不同知识库中的问答，最近更新的会话会排在最前面。
      </p>

      {conversationsQuery.isLoading && (
        <div className="mt-10 flex items-center gap-3 text-sm text-slate-500">
          <RefreshCw className="animate-spin" size={18} /> 正在加载对话…
        </div>
      )}

      {conversationsQuery.isError && (
        <div className="mt-8 rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
          {conversationsQuery.error.message}
        </div>
      )}

      {conversationsQuery.data?.items.length === 0 && (
        <div className="mt-10 rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <MessageSquareText className="mx-auto text-slate-300" size={34} />
          <h2 className="mt-4 font-semibold text-slate-800">还没有对话</h2>
          <p className="mt-2 text-sm text-slate-500">
            进入一个知识库并创建对话后，它会显示在这里。
          </p>
        </div>
      )}

      <section className="mt-8 grid gap-4">
        {conversationsQuery.data?.items.map((conversation) => (
          <article
            key={conversation.id}
            className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:flex-row sm:items-center"
          >
            <Link
              className="min-w-0 flex-1"
              to={`/knowledge-bases/${conversation.knowledge_base_id}/conversations/${conversation.id}`}
            >
              <h2 className="truncate font-semibold text-slate-900 hover:text-indigo-600">
                {conversation.title ?? '新对话'}
              </h2>
              <p className="mt-1 truncate text-sm text-slate-500">
                {conversation.knowledge_base_name}
              </p>
              <p className="mt-3 flex items-center gap-1.5 text-xs text-slate-400">
                <Clock3 size={14} /> {formatDate(conversation.updated_at)}
              </p>
            </Link>
            <button
              type="button"
              aria-label={`删除会话 ${conversation.title ?? '新对话'}`}
              disabled={deleteMutation.isPending}
              onClick={() => {
                if (window.confirm('确定删除这个会话吗？此操作无法撤销。')) {
                  deleteMutation.mutate({
                    knowledgeBaseId: conversation.knowledge_base_id,
                    conversationId: conversation.id,
                  })
                }
              }}
              className="inline-flex size-10 items-center justify-center rounded-xl text-slate-400 transition hover:bg-rose-50 hover:text-rose-600 disabled:opacity-50"
            >
              <Trash2 size={18} />
            </button>
          </article>
        ))}
      </section>
    </div>
  )
}
