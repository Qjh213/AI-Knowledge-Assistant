import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MarkdownMessage } from './MarkdownMessage'


describe('MarkdownMessage', () => {
  it('renders headings, lists, tables, and safe links', () => {
    render(
      <MarkdownMessage
        content={`# 标题

- 第一项
- 第二项

| 名称 | 说明 |
| --- | --- |
| Milvus | 向量数据库 |

[官方文档](https://example.com)`}
      />,
    )

    expect(screen.getByRole('heading', { name: '标题' })).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '官方文档' })).toHaveAttribute(
      'target',
      '_blank',
    )
  })

  it('does not render raw HTML from model output', () => {
    render(<MarkdownMessage content={'<script>alert("xss")</script>'} />)

    expect(document.querySelector('script')).not.toBeInTheDocument()
  })

  it('copies a code block', async () => {
    const user = userEvent.setup()
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })

    render(<MarkdownMessage content={'```python\nprint("hello")\n```'} />)
    await user.click(screen.getByRole('button', { name: '复制代码' }))

    expect(writeText).toHaveBeenCalledWith('print("hello")')
  })
})
