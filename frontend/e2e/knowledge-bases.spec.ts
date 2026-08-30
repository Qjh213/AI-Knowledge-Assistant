import { expect, test } from '@playwright/test'


const now = '2026-08-31T00:00:00Z'

test('renders dashboard statistics and knowledge bases', async ({ page }) => {
  await page.route('**/api/v1/dashboard/overview', (route) =>
    route.fulfill({
      json: {
        knowledge_base_count: 2,
        processed_document_count: 5,
        conversation_count: 3,
      },
    }),
  )
  await page.route('**/api/v1/knowledge-bases?**', (route) =>
    route.fulfill({
      json: {
        items: [
          {
            id: 'kb-1',
            name: '产品知识库',
            description: '产品说明和使用手册',
            created_at: now,
            updated_at: now,
          },
          {
            id: 'kb-2',
            name: '技术知识库',
            description: null,
            created_at: now,
            updated_at: now,
          },
        ],
        total: 2,
        offset: 0,
        limit: 20,
      },
    }),
  )

  await page.goto('/knowledge-bases')

  await expect(page.getByRole('heading', { name: '管理你的知识库' })).toBeVisible()
  await expect(page.getByText('产品知识库')).toBeVisible()
  await expect(page.getByText('技术知识库')).toBeVisible()
  await expect(
    page.locator('article').filter({ hasText: '已处理文档' }).getByText('5'),
  ).toBeVisible()
  await expect(
    page.locator('article').filter({ hasText: '对话总数' }).getByText('3'),
  ).toBeVisible()
})

test('creates a knowledge base and refreshes the dashboard', async ({ page }) => {
  const items: Array<Record<string, unknown>> = []

  await page.route('**/api/v1/dashboard/overview', (route) =>
    route.fulfill({
      json: {
        knowledge_base_count: items.length,
        processed_document_count: 0,
        conversation_count: 0,
      },
    }),
  )
  await page.route('**/api/v1/knowledge-bases**', async (route) => {
    const request = route.request()

    if (request.method() === 'POST') {
      const body = request.postDataJSON() as {
        name: string
        description: string | null
      }
      const created = {
        id: 'kb-created',
        name: body.name,
        description: body.description,
        created_at: now,
        updated_at: now,
      }
      items.push(created)
      await route.fulfill({ status: 201, json: created })
      return
    }

    await route.fulfill({
      json: {
        items,
        total: items.length,
        offset: 0,
        limit: 20,
      },
    })
  })

  await page.goto('/knowledge-bases')
  await page.getByRole('button', { name: '创建知识库' }).click()
  await page.getByLabel(/名称/).fill('测试知识库')
  await page.getByLabel(/描述/).fill('浏览器自动化测试')
  await page.getByRole('button', { name: '创建', exact: true }).click()

  await expect(page.getByText('知识库创建成功。')).toBeVisible()
  await expect(page.getByText('测试知识库')).toBeVisible()
  await expect(
    page.locator('article').filter({ hasText: '知识库' }).getByText('1'),
  ).toBeVisible()
})
