import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createKnowledgeBase } from '../../api/knowledgeBases'
import { ToastProvider } from '../feedback/ToastProvider'
import { CreateKnowledgeBaseDialog } from './CreateKnowledgeBaseDialog'


vi.mock('../../api/knowledgeBases', () => ({
  createKnowledgeBase: vi.fn(),
}))

const mockedCreateKnowledgeBase = vi.mocked(createKnowledgeBase)

function renderDialog(onClose = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  })

  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <CreateKnowledgeBaseDialog open onClose={onClose} />
      </ToastProvider>
    </QueryClientProvider>,
  )

  return { onClose }
}

beforeEach(() => {
  mockedCreateKnowledgeBase.mockReset()
})

describe('CreateKnowledgeBaseDialog', () => {
  it('rejects an empty knowledge base name before calling the API', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('button', { name: '创建' }))

    expect(screen.getByText('请输入知识库名称。')).toBeInTheDocument()
    expect(mockedCreateKnowledgeBase).not.toHaveBeenCalled()
  })

  it('normalizes input, closes, and shows a success notification', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    mockedCreateKnowledgeBase.mockResolvedValue({
      id: 'kb-1',
      name: '产品手册',
      description: '使用说明',
      created_at: '2026-08-31T00:00:00Z',
      updated_at: '2026-08-31T00:00:00Z',
    })
    renderDialog(onClose)

    await user.type(screen.getByLabelText(/名称/), '  产品手册  ')
    await user.type(screen.getByLabelText(/描述/), '  使用说明  ')
    await user.click(screen.getByRole('button', { name: '创建' }))

    expect(mockedCreateKnowledgeBase).toHaveBeenCalledOnce()
    expect(mockedCreateKnowledgeBase.mock.calls[0]?.[0]).toEqual({
      name: '产品手册',
      description: '使用说明',
    })
    expect(await screen.findByText('知识库创建成功。')).toBeInTheDocument()
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('keeps the API error visible when creation fails', async () => {
    const user = userEvent.setup()
    mockedCreateKnowledgeBase.mockRejectedValue(new Error('名称已经存在'))
    renderDialog()

    await user.type(screen.getByLabelText(/名称/), '重复名称')
    await user.click(screen.getByRole('button', { name: '创建' }))

    expect(await screen.findAllByText('名称已经存在')).toHaveLength(2)
  })
})
