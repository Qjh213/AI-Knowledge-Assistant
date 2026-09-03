import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getDashboardOverview } from '../api/dashboard'
import { getKnowledgeBases } from '../api/knowledgeBases'
import { ToastProvider } from '../components/feedback/ToastProvider'
import { KnowledgeBasesPage } from './KnowledgeBasesPage'


vi.mock('../api/dashboard', () => ({
  getDashboardOverview: vi.fn(),
}))

vi.mock('../api/knowledgeBases', () => ({
  getKnowledgeBases: vi.fn(),
  createKnowledgeBase: vi.fn(),
}))

const mockedGetDashboardOverview = vi.mocked(getDashboardOverview)
const mockedGetKnowledgeBases = vi.mocked(getKnowledgeBases)

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
        <MemoryRouter>
          <KnowledgeBasesPage />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  // jsdom does not implement the browser's modal dialog methods.
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
  mockedGetDashboardOverview.mockReset()
  mockedGetKnowledgeBases.mockReset()
})

describe('KnowledgeBasesPage', () => {
  it('renders real overview statistics and knowledge bases', async () => {
    mockedGetDashboardOverview.mockResolvedValue({
      knowledge_base_count: 2,
      processed_document_count: 5,
      conversation_count: 3,
    })
    mockedGetKnowledgeBases.mockResolvedValue({
      items: [
        {
          id: 'kb-1',
          name: '产品知识库',
          description: '产品说明和使用手册',
          created_at: '2026-08-31T08:00:00Z',
          updated_at: '2026-08-31T08:00:00Z',
        },
        {
          id: 'kb-2',
          name: '技术知识库',
          description: null,
          created_at: '2026-08-31T09:00:00Z',
          updated_at: '2026-08-31T09:00:00Z',
        },
      ],
      total: 2,
      offset: 0,
      limit: 20,
    })

    renderPage()

    const knowledgeBaseCard = screen.getByText('知识库').closest('article')
    const documentCard = screen.getByText('已处理文档').closest('article')
    const conversationCard = screen.getByText('对话总数').closest('article')

    expect(knowledgeBaseCard).not.toBeNull()
    expect(documentCard).not.toBeNull()
    expect(conversationCard).not.toBeNull()
    expect(await within(knowledgeBaseCard!).findByText('2')).toBeInTheDocument()
    expect(await within(documentCard!).findByText('5')).toBeInTheDocument()
    expect(await within(conversationCard!).findByText('3')).toBeInTheDocument()
    expect(await screen.findByText('产品知识库')).toBeInTheDocument()
    expect(screen.getByText('技术知识库')).toBeInTheDocument()
    expect(screen.getByText('暂无描述')).toBeInTheDocument()
  })

  it('renders the empty state when no knowledge base exists', async () => {
    mockedGetDashboardOverview.mockResolvedValue({
      knowledge_base_count: 0,
      processed_document_count: 0,
      conversation_count: 0,
    })
    mockedGetKnowledgeBases.mockResolvedValue({
      items: [],
      total: 0,
      offset: 0,
      limit: 20,
    })

    renderPage()

    expect(await screen.findByText('创建第一个知识库')).toBeInTheDocument()
  })

  it('opens the guide, closes it, and starts creating a knowledge base', async () => {
    const user = userEvent.setup()
    mockedGetDashboardOverview.mockResolvedValue({ knowledge_base_count: 0, processed_document_count: 0, conversation_count: 0 })
    mockedGetKnowledgeBases.mockResolvedValue({ items: [], total: 0, offset: 0, limit: 20 })
    renderPage()
    const trigger = await screen.findByRole('button', { name: '查看使用指南' })
    await user.click(trigger)
    let guide = screen.getByRole('dialog', { name: '知识库使用指南' })
    expect(within(guide).getAllByRole('listitem')).toHaveLength(4)
    expect(within(guide).getByText(/只有处理完成的文件才能用于问答/)).toBeInTheDocument()
    await user.click(within(guide).getByRole('button', { name: '关闭使用指南' }))
    expect(screen.queryByRole('dialog', { name: '知识库使用指南' })).not.toBeInTheDocument()
    await user.click(trigger)
    guide = screen.getByRole('dialog', { name: '知识库使用指南' })
    fireEvent(guide, new Event('cancel', { bubbles: true, cancelable: true }))
    expect(screen.queryByRole('dialog', { name: '知识库使用指南' })).not.toBeInTheDocument()
    await user.click(trigger)
    await user.click(screen.getByRole('button', { name: '我知道了' }))
    expect(screen.queryByRole('dialog', { name: '知识库使用指南' })).not.toBeInTheDocument()
    await user.click(trigger)
    await user.click(screen.getByRole('button', { name: '开始创建' }))
    expect(screen.queryByRole('dialog', { name: '知识库使用指南' })).not.toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: '创建知识库' })).toBeInTheDocument()
  })

  it('shows the backend error message when loading fails', async () => {
    mockedGetDashboardOverview.mockResolvedValue({
      knowledge_base_count: 0,
      processed_document_count: 0,
      conversation_count: 0,
    })
    mockedGetKnowledgeBases.mockRejectedValue(new Error('后端连接失败'))

    renderPage()

    expect(await screen.findByText('无法连接后端服务')).toBeInTheDocument()
    expect(screen.getByText('后端连接失败')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重新加载' })).toBeInTheDocument()
  })
})
