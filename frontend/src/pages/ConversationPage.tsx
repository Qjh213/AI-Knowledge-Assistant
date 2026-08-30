import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  BookOpen,
  Bot,
  FileText,
  LoaderCircle,
  Send,
  Square,
  User,
} from 'lucide-react'
import { useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  getConversation,
  getMessages,
  streamMessage,
} from '../api/conversations'
import { getKnowledgeBase } from '../api/knowledgeBases'
import type { Message, RagCitation } from '../types/conversation'

export function ConversationPage() {
  const { knowledgeBaseId, conversationId } = useParams()
  const queryClient = useQueryClient()
  const [content, setContent] = useState('')
  const [streamedUserMessage, setStreamedUserMessage] =
    useState<Message | null>(null)
  const [streamedAnswer, setStreamedAnswer] = useState('')
  const [streamedCitations, setStreamedCitations] = useState<RagCitation[]>([])
  const abortControllerRef = useRef<AbortController | null>(null)

  const idsReady = Boolean(knowledgeBaseId && conversationId)
  const knowledgeBaseQuery = useQuery({
    queryKey: ['knowledge-base', knowledgeBaseId],
    queryFn: () => getKnowledgeBase(knowledgeBaseId!),
    enabled: Boolean(knowledgeBaseId),
  })
  const conversationQuery = useQuery({
    queryKey: ['conversation', knowledgeBaseId, conversationId],
    queryFn: () => getConversation(knowledgeBaseId!, conversationId!),
    enabled: idsReady,
  })
  const messagesQuery = useQuery({
    queryKey: ['messages', knowledgeBaseId, conversationId],
    queryFn: () => getMessages(knowledgeBaseId!, conversationId!),
    enabled: idsReady,
  })

  const sendMutation = useMutation({
    mutationFn: async (message: string) => {
      const controller = new AbortController()
      abortControllerRef.current = controller

      await streamMessage(
        knowledgeBaseId!,
        conversationId!,
        {
          content: message,
          retrieval_limit: 5,
          min_score: 0.3,
        },
        ({ event, data }) => {
          switch (event) {
            case 'user_message':
              setStreamedUserMessage(data.message)
              break
            case 'citations':
              setStreamedCitations(data.citations)
              break
            case 'token':
              setStreamedAnswer((current) => current + data.content)
              break
            case 'done':
              setStreamedAnswer(data.message.content)
              setStreamedCitations(data.message.sources ?? [])
              break
            case 'error':
              break
          }
        },
        controller.signal,
      )
    },
    onMutate: () => {
      setContent('')
      setStreamedUserMessage(null)
      setStreamedAnswer('')
      setStreamedCitations([])
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ['messages', knowledgeBaseId, conversationId],
        }),
        queryClient.invalidateQueries({
          queryKey: ['conversation', knowledgeBaseId, conversationId],
        }),
        queryClient.invalidateQueries({
          queryKey: ['conversations', knowledgeBaseId],
        }),
      ])
      setStreamedUserMessage(null)
      setStreamedAnswer('')
      setStreamedCitations([])
    },
    onError: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['messages', knowledgeBaseId, conversationId],
      })
      setStreamedUserMessage(null)
      setStreamedAnswer('')
      setStreamedCitations([])
    },
    onSettled: () => {
      abortControllerRef.current = null
    },
  })

  function submitMessage() {
    const normalized = content.trim()
    if (normalized && !sendMutation.isPending) {
      sendMutation.mutate(normalized)
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    submitMessage()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submitMessage()
    }
  }

  const messages = messagesQuery.data?.items ?? []
  const streamingAssistant: Message | null = streamedAnswer
    ? {
        id: 'streaming-assistant',
        conversation_id: conversationId ?? '',
        role: 'assistant',
        content: streamedAnswer,
        sources: streamedCitations,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }
    : null
  const visibleMessages = [
    ...messages,
    ...(streamedUserMessage ? [streamedUserMessage] : []),
    ...(streamingAssistant ? [streamingAssistant] : []),
  ]

  return (
    <div className="flex min-h-[calc(100vh-6rem)] flex-col">
      <header className="flex items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div className="min-w-0">
          <Link
            to={`/knowledge-bases/${knowledgeBaseId}`}
            className="inline-flex items-center gap-2 text-xs font-medium text-slate-400 hover:text-indigo-600"
          >
            <ArrowLeft size={15} />
            {knowledgeBaseQuery.data?.name || '返回知识库'}
          </Link>
          <h1 className="mt-2 truncate text-xl font-semibold text-slate-950">
            {conversationQuery.data?.title || '新对话'}
          </h1>
        </div>
        <div className="hidden items-center gap-2 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 sm:flex">
          <span className="size-2 rounded-full bg-emerald-500" />
          知识库已连接
        </div>
      </header>

      <section className="flex-1 py-6">
        {(messagesQuery.isPending || conversationQuery.isPending) && (
          <div className="flex justify-center py-16 text-slate-400">
            <LoaderCircle className="animate-spin" />
          </div>
        )}

        {messagesQuery.isError && (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
            {messagesQuery.error instanceof Error
              ? messagesQuery.error.message
              : '无法加载消息历史。'}
          </div>
        )}

        {messagesQuery.isSuccess && messages.length === 0 && (
          <div className="mx-auto flex max-w-lg flex-col items-center py-16 text-center">
            <div className="grid size-16 place-items-center rounded-2xl bg-indigo-50 text-indigo-600">
              <BookOpen size={28} />
            </div>
            <h2 className="mt-5 text-xl font-semibold text-slate-950">
              从知识库开始提问
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              助手会检索已处理文档，依据相关内容回答并标注引用来源。
            </p>
          </div>
        )}

        <div className="mx-auto space-y-6">
          {visibleMessages.map((message) => {
            const isUser = message.role === 'user'
            return (
              <article
                key={message.id}
                className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}
              >
                {!isUser && (
                  <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-indigo-600 text-white">
                    <Bot size={18} />
                  </div>
                )}
                <div className={`max-w-3xl ${isUser ? 'order-first' : ''}`}>
                  <div
                    className={`whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-7 ${
                      isUser
                        ? 'rounded-br-md bg-slate-900 text-white'
                        : 'rounded-bl-md border border-slate-200 bg-white text-slate-700 shadow-sm'
                    }`}
                  >
                    {message.content}
                  </div>

                  {!isUser && message.sources && message.sources.length > 0 && (
                    <details className="mt-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm">
                      <summary className="cursor-pointer font-medium text-slate-600">
                        {message.sources.length} 个引用来源
                      </summary>
                      <div className="mt-3 space-y-3">
                        {message.sources.map((source) => (
                          <div
                            key={source.chunk_id}
                            className="rounded-xl bg-slate-50 p-3"
                          >
                            <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
                              <FileText size={14} />
                              [{source.reference}] {source.original_filename}
                              {source.page_number !== null &&
                                ` · 第 ${source.page_number} 页`}
                            </div>
                            <p className="mt-2 text-xs leading-5 text-slate-500">
                              {source.content}
                            </p>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
                {isUser && (
                  <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-slate-200 text-slate-600">
                    <User size={18} />
                  </div>
                )}
              </article>
            )
          })}

          {sendMutation.isPending && !streamingAssistant && (
            <div className="flex items-center gap-3">
              <div className="grid size-9 place-items-center rounded-xl bg-indigo-600 text-white">
                <Bot size={18} />
              </div>
              <div className="flex items-center gap-2 rounded-2xl rounded-bl-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                <LoaderCircle size={16} className="animate-spin" />
                正在检索并生成回答…
              </div>
            </div>
          )}
        </div>
      </section>

      <footer className="sticky bottom-0 border-t border-slate-200 bg-[#f5f7fb]/95 pt-4 pb-2 backdrop-blur">
        {sendMutation.isError && (
          <p className="mb-3 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {sendMutation.error instanceof DOMException &&
            sendMutation.error.name === 'AbortError'
              ? '已停止生成回答。'
              : sendMutation.error instanceof Error
                ? sendMutation.error.message
              : '发送消息失败，请重试。'}
          </p>
        )}
        <form
          onSubmit={handleSubmit}
          className="flex items-end gap-3 rounded-2xl border border-slate-200 bg-white p-2 shadow-lg shadow-slate-200/50 focus-within:border-indigo-300"
        >
          <textarea
            value={content}
            rows={1}
            maxLength={4000}
            disabled={sendMutation.isPending}
            onChange={(event) => setContent(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="询问知识库中的内容…"
            className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-3 py-2.5 text-sm leading-6 outline-none placeholder:text-slate-400 disabled:opacity-60"
          />
          {sendMutation.isPending ? (
            <button
              type="button"
              aria-label="停止生成"
              onClick={() => abortControllerRef.current?.abort()}
              className="grid size-11 shrink-0 place-items-center rounded-xl bg-slate-900 text-white transition hover:bg-slate-700"
            >
              <Square size={16} fill="currentColor" />
            </button>
          ) : (
            <button
              type="submit"
              aria-label="发送消息"
              disabled={!content.trim()}
              className="grid size-11 shrink-0 place-items-center rounded-xl bg-indigo-600 text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
            >
              <Send size={19} />
            </button>
          )}
        </form>
        <p className="mt-2 text-center text-[11px] text-slate-400">
          Enter 发送，Shift + Enter 换行。回答仅依据知识库资料生成。
        </p>
      </footer>
    </div>
  )
}
