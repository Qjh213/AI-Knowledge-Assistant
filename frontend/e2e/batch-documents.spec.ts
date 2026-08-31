import { expect, test } from '@playwright/test'


const now = '2026-08-31T00:00:00Z'

function document(id: string, name: string) {
  return {
    id,
    knowledge_base_id: 'kb-batch',
    original_filename: name,
    mime_type: name.endsWith('.pdf') ? 'application/pdf' : 'text/plain',
    file_size: 1024,
    checksum: id.repeat(16).slice(0, 64),
    status: 'pending',
    error_message: null,
    chunk_count: 0,
    parser: 'local',
    external_task_id: null,
    processing_progress: 0,
    created_at: now,
    updated_at: now,
  }
}

test('supports multi-file selection and batch processing controls', async ({
  page,
}) => {
  const documents = [
    document('doc-1', 'notes.txt'),
    document('doc-2', 'guide.pdf'),
    document('doc-3', 'manual.pdf'),
  ]
  const processedIds: string[] = []

  await page.route(
    /\/api\/v1\/knowledge-bases\/kb-batch$/,
    (route) =>
      route.fulfill({
        json: {
          id: 'kb-batch',
          name: '批量处理测试库',
          description: 'Playwright batch test',
          created_at: now,
          updated_at: now,
        },
      }),
  )
  await page.route(
    /\/api\/v1\/knowledge-bases\/kb-batch\/documents\?.*/,
    (route) =>
      route.fulfill({
        json: {
          items: documents,
          total: documents.length,
          offset: 0,
          limit: 100,
        },
      }),
  )
  await page.route(
    /\/api\/v1\/knowledge-bases\/kb-batch\/documents\/[^/]+\/process$/,
    async (route) => {
      const id = route.request().url().split('/').at(-2)!
      processedIds.push(id)
      const source = documents.find((item) => item.id === id)!
      await route.fulfill({
        json: {
          ...source,
          status: 'completed',
          chunk_count: 1,
          processing_progress: 100,
        },
      })
    },
  )
  await page.route(
    /\/api\/v1\/knowledge-bases\/kb-batch\/conversations\?.*/,
    (route) =>
      route.fulfill({
        json: { items: [], total: 0, offset: 0, limit: 20 },
      }),
  )

  await page.goto('/knowledge-bases/kb-batch')

  const fileInput = page.locator('input[type="file"]')
  await expect(fileInput).toHaveAttribute('multiple', '')
  await expect(
    page.getByRole('button', { name: '批量本地处理 (3)' }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: '批量 MinerU (2)' }),
  ).toBeVisible()

  await page.getByRole('button', { name: '批量本地处理 (3)' }).click()

  await expect(
    page.getByText('已启动 3 个文档的批量处理。'),
  ).toBeVisible()
  expect(processedIds.sort()).toEqual(['doc-1', 'doc-2', 'doc-3'])
})
