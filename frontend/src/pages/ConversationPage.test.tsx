import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  getConversation,
  getMessages,
  streamMessage,
} from '../api/conversations'
import { getKnowledgeBase } from '../api/knowledgeBases'
import { ToastProvider } from '../components/feedback/ToastProvider'
import type { Message, RagCitation } from '../types/conversation'
import { ConversationPage } from './ConversationPage'


vi.mock('../api/conversations', () => ({
  getConversation: vi.fn(),
  getMessages: vi.fn(),
  streamMessage: vi.fn(),
}))

vi.mock('../api/knowledgeBases', () => ({
  getKnowledgeBase: vi.fn(),
}))

const mockedGetConversation = vi.mocked(getConversation)
const mockedGetKnowledgeBase = vi.mocked(getKnowledgeBase)
const mockedGetMessages = vi.mocked(getMessages)
const mockedStreamMessage = vi.mocked(streamMessage)

const now = '2026-08-31T00:00:00Z'
const citation: RagCitation = {
  reference: 1,
  chunk_id: 'chunk-1',
  document_id: 'document-1',
  original_filename: 'milvus.md',
  page_number: 2,
  content: 'Milvus 是一个向量数据库。',
  score: 0.91,
}

function message(
  id: string,
  role: Message['role'],
  content: string,
  sources: RagCitation[] | null = null,
): Message {
  return {
    id,
    conversation_id: 'conversation-1',
    role,
    content,
    sources,
    created_at: now,
    updated_at: now,
  }
}

function prepareQueries(items: Message[] = []) {
  mockedGetKnowledgeBase.mockResolvedValue({
    id: 'knowledge-base-1',
    name: '技术知识库',
    description: null,
    created_at: now,
    updated_at: now,
  })
  mockedGetConversation.mockResolvedValue({
    id: 'conversation-1',
    knowledge_base_id: 'knowledge-base-1',
    title: 'Milvus 对话',
    created_at: now,
    updated_at: now,
  })
  mockedGetMessages.mockResolvedValue({
    items,
    total: items.length,
    offset: 0,
    limit: 100,
  })
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter
          initialEntries={[
            '/knowledge-bases/knowledge-base-1/conversations/conversation-1',
          ]}
        >
          <Routes>
            <Route
              path="/knowledge-bases/:knowledgeBaseId/conversations/:conversationId"
              element={<ConversationPage />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  mockedGetConversation.mockReset()
  mockedGetKnowledgeBase.mockReset()
  mockedGetMessages.mockReset()
  mockedStreamMessage.mockReset()
})

describe('ConversationPage', () => {
  it('renders saved conversation history and citations', async () => {
    prepareQueries([
      message('user-1', 'user', 'Milvus 是什么？'),
      message('assistant-1', 'assistant', 'Milvus 是向量数据库。[1]', [
        citation,
      ]),
    ])

    renderPage()

    expect(await screen.findByText('Milvus 对话')).toBeInTheDocument()
    expect(screen.getByText('Milvus 是什么？')).toBeInTheDocument()
    expect(screen.getByText('Milvus 是向量数据库。[1]')).toBeInTheDocument()
    expect(screen.getByText('1 个引用来源')).toBeInTheDocument()
  })

  it('renders streamed tokens and source citations', async () => {
    const user = userEvent.setup()
    prepareQueries([])
    const userMessage = message('user-1', 'user', 'Milvus 是什么？')
    const assistantMessage = message(
      'assistant-1',
      'assistant',
      'Milvus 是向量数据库。[1]',
      [citation],
    )
    mockedGetMessages
      .mockResolvedValueOnce({
        items: [],
        total: 0,
        offset: 0,
        limit: 100,
      })
      .mockResolvedValue({
        items: [userMessage, assistantMessage],
        total: 2,
        offset: 0,
        limit: 100,
      })
    mockedStreamMessage.mockImplementation(
      async (_knowledgeBaseId, _conversationId, data, onEvent) => {
        onEvent({
          event: 'user_message',
          data: { message: { ...userMessage, content: data.content } },
        })
        onEvent({ event: 'citations', data: { citations: [citation] } })
        onEvent({ event: 'token', data: { content: 'Milvus 是' } })
        onEvent({ event: 'token', data: { content: '向量数据库。[1]' } })
        onEvent({ event: 'done', data: { message: assistantMessage } })
      },
    )
    renderPage()

    const input = await screen.findByPlaceholderText('询问知识库中的内容…')
    await user.type(input, 'Milvus 是什么？')
    await user.click(screen.getByRole('button', { name: '发送消息' }))

    expect(mockedStreamMessage).toHaveBeenCalledOnce()
    expect(await screen.findByText('Milvus 是向量数据库。[1]')).toBeInTheDocument()
  })

  it('aborts an active streaming response', async () => {
    const user = userEvent.setup()
    prepareQueries([])
    mockedStreamMessage.mockImplementation(
      (_knowledgeBaseId, _conversationId, _data, _onEvent, signal) =>
        new Promise<void>((_resolve, reject) => {
          signal?.addEventListener('abort', () => {
            reject(new DOMException('Aborted', 'AbortError'))
          })
        }),
    )
    renderPage()

    await user.type(
      await screen.findByPlaceholderText('询问知识库中的内容…'),
      '停止测试',
    )
    await user.click(screen.getByRole('button', { name: '发送消息' }))
    await user.click(await screen.findByRole('button', { name: '停止生成' }))

    expect(await screen.findByText('已停止生成回答。')).toBeInTheDocument()
  })
})
