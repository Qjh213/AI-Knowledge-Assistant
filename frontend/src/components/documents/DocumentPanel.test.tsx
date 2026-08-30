import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  deleteDocument,
  getDocuments,
  processDocument,
  uploadDocument,
} from '../../api/documents'
import type { Document, DocumentStatus } from '../../types/document'
import { ToastProvider } from '../feedback/ToastProvider'
import { DocumentPanel } from './DocumentPanel'


vi.mock('../../api/documents', () => ({
  deleteDocument: vi.fn(),
  getDocuments: vi.fn(),
  processDocument: vi.fn(),
  uploadDocument: vi.fn(),
}))

const mockedDeleteDocument = vi.mocked(deleteDocument)
const mockedGetDocuments = vi.mocked(getDocuments)
const mockedProcessDocument = vi.mocked(processDocument)
const mockedUploadDocument = vi.mocked(uploadDocument)

function createDocument(status: DocumentStatus = 'pending'): Document {
  return {
    id: 'document-1',
    knowledge_base_id: 'knowledge-base-1',
    original_filename: 'guide.txt',
    mime_type: 'text/plain',
    file_size: 1536,
    checksum: 'checksum',
    status,
    error_message: null,
    chunk_count: status === 'completed' ? 4 : 0,
    created_at: '2026-08-31T00:00:00Z',
    updated_at: '2026-08-31T00:00:00Z',
  }
}

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <DocumentPanel knowledgeBaseId="knowledge-base-1" />
      </ToastProvider>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  mockedDeleteDocument.mockReset()
  mockedGetDocuments.mockReset()
  mockedProcessDocument.mockReset()
  mockedUploadDocument.mockReset()
})

describe('DocumentPanel', () => {
  it('renders document metadata and completed status', async () => {
    mockedGetDocuments.mockResolvedValue({
      items: [createDocument('completed')],
      total: 1,
      offset: 0,
      limit: 100,
    })

    renderPanel()

    expect(await screen.findByText('guide.txt')).toBeInTheDocument()
    expect(screen.getByText('1.5 KB')).toBeInTheDocument()
    expect(screen.getByText('4 个分块')).toBeInTheDocument()
    expect(screen.getByText('处理完成')).toBeInTheDocument()
  })

  it('uploads a selected file and shows success feedback', async () => {
    const user = userEvent.setup()
    const uploaded = createDocument('pending')
    mockedGetDocuments.mockResolvedValue({
      items: [],
      total: 0,
      offset: 0,
      limit: 100,
    })
    mockedUploadDocument.mockResolvedValue(uploaded)
    const { container } = renderPanel()
    const input = container.querySelector<HTMLInputElement>('input[type="file"]')
    const file = new File(['知识库测试'], 'guide.txt', { type: 'text/plain' })

    expect(input).not.toBeNull()
    await user.upload(input!, file)

    expect(mockedUploadDocument).toHaveBeenCalledOnce()
    expect(mockedUploadDocument.mock.calls[0]?.[0]).toBe('knowledge-base-1')
    expect(mockedUploadDocument.mock.calls[0]?.[1]).toBe(file)
    expect(
      await screen.findByText('文档上传成功，请开始处理。'),
    ).toBeInTheDocument()
  })

  it('processes a pending document', async () => {
    const user = userEvent.setup()
    const pending = createDocument('pending')
    mockedGetDocuments.mockResolvedValue({
      items: [pending],
      total: 1,
      offset: 0,
      limit: 100,
    })
    mockedProcessDocument.mockResolvedValue(createDocument('completed'))
    renderPanel()

    await user.click(await screen.findByRole('button', { name: '开始处理' }))

    expect(mockedProcessDocument).toHaveBeenCalledWith(
      'knowledge-base-1',
      'document-1',
    )
    expect(await screen.findByText('文档处理完成。')).toBeInTheDocument()
  })

  it('deletes a document after confirmation', async () => {
    const user = userEvent.setup()
    const completed = createDocument('completed')
    mockedGetDocuments.mockResolvedValue({
      items: [completed],
      total: 1,
      offset: 0,
      limit: 100,
    })
    mockedDeleteDocument.mockResolvedValue(undefined)
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderPanel()

    await user.click(
      await screen.findByRole('button', { name: '删除 guide.txt' }),
    )

    await waitFor(() => {
      expect(mockedDeleteDocument).toHaveBeenCalled()
    })
    expect(mockedDeleteDocument.mock.calls[0]?.slice(0, 2)).toEqual([
      'knowledge-base-1',
      'document-1',
    ])
    expect(await screen.findByText('文档已删除。')).toBeInTheDocument()
  })
})
