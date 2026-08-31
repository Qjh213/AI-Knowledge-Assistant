import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  LoaderCircle,
  MessageSquarePlus,
  MessageSquareText,
  Trash2,
} from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  createConversation,
  deleteConversation,
  getConversations,
} from '../../api/conversations'
import type { Conversation } from '../../types/conversation'
import { useToast } from '../../lib/toast'
import { DeleteConversationDialog } from './DeleteConversationDialog'

interface ConversationPanelProps {
  knowledgeBaseId: string
}

export function ConversationPanel({ knowledgeBaseId }: ConversationPanelProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [conversationToDelete, setConversationToDelete] =
    useState<Conversation | null>(null)
  const conversationsQuery = useQuery({
    queryKey: ['conversations', knowledgeBaseId],
    queryFn: () => getConversations(knowledgeBaseId),
  })

  const createMutation = useMutation({
    mutationFn: () => createConversation(knowledgeBaseId),
    onSuccess: async (conversation) => {
      await queryClient.invalidateQueries({
        queryKey: ['conversations', knowledgeBaseId],
      })
      navigate(
        `/knowledge-bases/${knowledgeBaseId}/conversations/${conversation.id}`,
      )
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (conversationId: string) =>
      deleteConversation(knowledgeBaseId, conversationId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['conversations', knowledgeBaseId],
      })
      setConversationToDelete(null)
      showToast('会话已删除。')
    },
    onError: (error) => {
      showToast(
        error instanceof Error ? error.message : '删除会话失败。',
        'error',
      )
    },
  })

  return (
    <section className="mt-5 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm shadow-slate-200/40">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-xl bg-violet-50 text-violet-600">
            <MessageSquareText size={20} />
          </div>
          <div>
            <h2 className="font-semibold text-slate-950">知识对话</h2>
            <p className="text-xs text-slate-500">
              {conversationsQuery.data?.total ?? 0} 个会话
            </p>
          </div>
        </div>
        <button
          disabled={createMutation.isPending}
          onClick={() => createMutation.mutate()}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-indigo-200 bg-indigo-50 px-4 text-sm font-semibold text-indigo-700 transition hover:bg-indigo-100 disabled:opacity-60"
        >
          {createMutation.isPending ? (
            <LoaderCircle size={17} className="animate-spin" />
          ) : (
            <MessageSquarePlus size={17} />
          )}
          {createMutation.isPending ? '创建中' : '新建对话'}
        </button>
      </div>

      {createMutation.isError && (
        <p className="mt-4 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {createMutation.error instanceof Error
            ? createMutation.error.message
            : '创建会话失败。'}
        </p>
      )}

      {conversationsQuery.isPending && (
        <div className="mt-6 h-20 animate-pulse rounded-2xl bg-slate-50" />
      )}

      {conversationsQuery.isSuccess &&
        conversationsQuery.data.items.length === 0 && (
          <div className="mt-6 rounded-2xl border border-dashed border-slate-200 px-5 py-8 text-center">
            <p className="text-sm font-medium text-slate-700">还没有会话</p>
            <p className="mt-1 text-xs text-slate-400">
              创建会话后即可围绕知识库进行连续提问。
            </p>
          </div>
        )}

      {conversationsQuery.isSuccess &&
        conversationsQuery.data.items.length > 0 && (
          <div className="mt-6 grid gap-3 md:grid-cols-2">
            {conversationsQuery.data.items.map((conversation) => {
              const title = conversation.title || '新对话'
              return (
                <div key={conversation.id} className="flex items-center gap-2 rounded-2xl border border-slate-200 p-2 transition hover:border-indigo-200 hover:bg-indigo-50/40">
                  <Link
                    to={`/knowledge-bases/${knowledgeBaseId}/conversations/${conversation.id}`}
                    className="min-w-0 flex-1 rounded-xl px-2 py-2"
                  >
                    <p className="truncate text-sm font-semibold text-slate-900">{title}</p>
                    <p className="mt-1 text-xs text-slate-400">
                      更新于 {new Date(conversation.updated_at).toLocaleString('zh-CN')}
                    </p>
                  </Link>
                  <button
                    type="button"
                    aria-label={`删除会话 ${title}`}
                    onClick={() => {
                      deleteMutation.reset()
                      setConversationToDelete(conversation)
                    }}
                    className="grid size-9 shrink-0 place-items-center rounded-xl text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
                  >
                    <Trash2 size={17} />
                  </button>
                </div>
              )
            })}
          </div>
        )}

      <DeleteConversationDialog
        open={Boolean(conversationToDelete)}
        conversationTitle={conversationToDelete?.title || '新对话'}
        isPending={deleteMutation.isPending}
        errorMessage={
          deleteMutation.isError
            ? deleteMutation.error instanceof Error
              ? deleteMutation.error.message
              : '删除失败，请稍后重试。'
            : undefined
        }
        onClose={() => {
          if (!deleteMutation.isPending) setConversationToDelete(null)
        }}
        onConfirm={() => {
          if (conversationToDelete) deleteMutation.mutate(conversationToDelete.id)
        }}
      />
    </section>
  )
}
