import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  deleteDocument,
  getDocuments,
  processDocument,
  processDocumentWithMinerU,
  refreshMinerUDocument,
  uploadDocument,
} from '../../api/documents'
import type { Document, DocumentStatus } from '../../types/document'
import { ToastProvider } from '../feedback/ToastProvider'
import { DocumentPanel } from './DocumentPanel'


vi.mock('../../api/documents', () => ({
  deleteDocument: vi.fn(),
  getDocuments: vi.fn(),
  processDocument: vi.fn(),
  processDocumentWithMinerU: vi.fn(),
  refreshMinerUDocument: vi.fn(),
  uploadDocument: vi.fn(),
}))

const mockedDeleteDocument = vi.mocked(deleteDocument)
const mockedGetDocuments = vi.mocked(getDocuments)
const mockedProcessDocument = vi.mocked(processDocument)
const mockedProcessDocumentWithMinerU = vi.mocked(processDocumentWithMinerU)
const mockedRefreshMinerUDocument = vi.mocked(refreshMinerUDocument)
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
    parser: 'local',
    external_task_id: null,
    processing_progress: status === 'completed' ? 100 : 0,
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
  mockedProcessDocumentWithMinerU.mockReset()
  mockedRefreshMinerUDocument.mockReset()
  mockedUploadDocument.mockReset()
})

describe('DocumentPanel', () => {
  it('explains batch upload and processing limits', async () => {
    mockedGetDocuments.mockResolvedValue({
      items: [],
      total: 0,
      offset: 0,
      limit: 100,
    })

    renderPanel()

    expect(await screen.findByText('批量上传与处理规则')).toBeInTheDocument()
    expect(screen.getByText(/每个文件最大 20 MB/)).toBeInTheDocument()
    expect(screen.getByText(/上传最多同时进行 3 个/)).toBeInTheDocument()
    expect(screen.getByText(/本地处理最多同时进行 2 个/)).toBeInTheDocument()
    expect(screen.getByText(/MinerU 仅处理 PDF/)).toBeInTheDocument()
    expect(screen.getByText(/不限制本次选择总数/)).toBeInTheDocument()
  })

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
      await screen.findByText('已上传 1 个文档，请开始处理。'),
    ).toBeInTheDocument()
  })

  it('uploads multiple selected files', async () => {
    const user = userEvent.setup()
    mockedGetDocuments.mockResolvedValue({
      items: [],
      total: 0,
      offset: 0,
      limit: 100,
    })
    mockedUploadDocument.mockResolvedValue(createDocument('pending'))
    const { container } = renderPanel()
    const input = container.querySelector<HTMLInputElement>('input[type="file"]')
    const files = [
      new File(['one'], 'one.txt', { type: 'text/plain' }),
      new File(['two'], 'two.md', { type: 'text/markdown' }),
      new File(['three'], 'three.pdf', { type: 'application/pdf' }),
    ]

    expect(input).not.toBeNull()
    await user.upload(input!, files)

    await waitFor(() => {
      expect(mockedUploadDocument).toHaveBeenCalledTimes(3)
    })
    expect(mockedUploadDocument.mock.calls.map((call) => call[1])).toEqual(files)
    expect(
      await screen.findByText('已上传 3 个文档，请开始处理。'),
    ).toBeInTheDocument()
  })

  it('keeps successful uploads when one file fails', async () => {
    const user = userEvent.setup()
    mockedGetDocuments.mockResolvedValue({
      items: [],
      total: 0,
      offset: 0,
      limit: 100,
    })
    mockedUploadDocument
      .mockResolvedValueOnce(createDocument('pending'))
      .mockRejectedValueOnce(new Error('unsupported file'))
    const { container } = renderPanel()
    const input = container.querySelector<HTMLInputElement>('input[type="file"]')
    const files = [
      new File(['one'], 'one.txt', { type: 'text/plain' }),
      new File(['bad'], 'bad.pdf', { type: 'application/pdf' }),
    ]

    await user.upload(input!, files)

    expect(
      await screen.findByText('已上传 1 个，失败 1 个：bad.pdf'),
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

    await user.click(await screen.findByRole('button', { name: '本地处理' }))

    expect(mockedProcessDocument).toHaveBeenCalledWith(
      'knowledge-base-1',
      'document-1',
    )
    expect(await screen.findByText('文档处理完成。')).toBeInTheDocument()
  })

  it('processes all pending documents locally', async () => {
    const user = userEvent.setup()
    const first = createDocument('pending')
    const second = {
      ...createDocument('pending'),
      id: 'document-2',
      original_filename: 'notes.md',
    }
    mockedGetDocuments.mockResolvedValue({
      items: [first, second],
      total: 2,
      offset: 0,
      limit: 100,
    })
    mockedProcessDocument.mockResolvedValue(createDocument('completed'))
    renderPanel()

    await user.click(
      await screen.findByRole('button', { name: '批量本地处理 (2)' }),
    )

    await waitFor(() => {
      expect(mockedProcessDocument).toHaveBeenCalledTimes(2)
    })
    expect(mockedProcessDocument.mock.calls).toEqual([
      ['knowledge-base-1', 'document-1'],
      ['knowledge-base-1', 'document-2'],
    ])
    expect(
      await screen.findByText('已启动 2 个文档的批量处理。'),
    ).toBeInTheDocument()
  })

  it('submits only supported documents in a MinerU batch', async () => {
    const user = userEvent.setup()
    const textDocument = createDocument('pending')
    const pdfDocument = {
      ...createDocument('pending'),
      id: 'document-2',
      original_filename: 'guide.pdf',
    }
    const docxDocument = {
      ...createDocument('pending'),
      id: 'document-3',
      original_filename: 'manual.docx',
    }
    mockedGetDocuments.mockResolvedValue({
      items: [textDocument, pdfDocument, docxDocument],
      total: 3,
      offset: 0,
      limit: 100,
    })
    mockedProcessDocumentWithMinerU.mockResolvedValue({
      ...pdfDocument,
      status: 'processing',
      parser: 'mineru',
    })
    renderPanel()

    await user.click(
      await screen.findByRole('button', { name: '批量 MinerU (2)' }),
    )

    await waitFor(() => {
      expect(mockedProcessDocumentWithMinerU).toHaveBeenCalledTimes(2)
    })
    expect(mockedProcessDocumentWithMinerU.mock.calls).toEqual([
      ['knowledge-base-1', 'document-2'],
      ['knowledge-base-1', 'document-3'],
    ])
  })

  it('submits a PDF document to MinerU', async () => {
    const user = userEvent.setup()
    const pending = {
      ...createDocument('pending'),
      original_filename: 'guide.pdf',
      mime_type: 'application/pdf',
    }
    mockedGetDocuments.mockResolvedValue({
      items: [pending],
      total: 1,
      offset: 0,
      limit: 100,
    })
    mockedProcessDocumentWithMinerU.mockResolvedValue({
      ...pending,
      status: 'processing',
      parser: 'mineru',
      external_task_id: 'batch-123',
    })
    renderPanel()

    await user.click(await screen.findByRole('button', { name: 'MinerU 解析' }))

    expect(mockedProcessDocumentWithMinerU).toHaveBeenCalledWith(
      'knowledge-base-1',
      'document-1',
    )
    expect(
      await screen.findByText('文档已提交 MinerU，正在解析。'),
    ).toBeInTheDocument()
  })

  it('refreshes a processing MinerU document', async () => {
    const processing: Document = {
      ...createDocument('processing'),
      original_filename: 'guide.pdf',
      mime_type: 'application/pdf',
      parser: 'mineru',
      external_task_id: 'batch-123',
      processing_progress: 45,
    }
    const completed: Document = {
      ...processing,
      status: 'completed',
      processing_progress: 100,
      chunk_count: 3,
    }
    mockedGetDocuments.mockResolvedValue({
      items: [processing],
      total: 1,
      offset: 0,
      limit: 100,
    })
    mockedRefreshMinerUDocument.mockResolvedValue(completed)

    renderPanel()

    await waitFor(() => {
      expect(mockedRefreshMinerUDocument).toHaveBeenCalledWith(
        'knowledge-base-1',
        'document-1',
      )
    }, { timeout: 4_000 })
    expect(await screen.findByText('处理完成')).toBeInTheDocument()
    expect(screen.getByText('100%')).toBeInTheDocument()
    expect(screen.getByText('3 个分块')).toBeInTheDocument()
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
