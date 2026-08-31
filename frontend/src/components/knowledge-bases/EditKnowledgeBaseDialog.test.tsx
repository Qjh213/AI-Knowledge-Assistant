import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { EditKnowledgeBaseDialog } from './EditKnowledgeBaseDialog'

describe('EditKnowledgeBaseDialog', () => {
  it('shows the current name and submits a normalized name', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()

    render(
      <EditKnowledgeBaseDialog
        open
        currentName="原知识库"
        isPending={false}
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />,
    )

    const input = screen.getByLabelText('名称')
    expect(input).toHaveValue('原知识库')
    await user.clear(input)
    await user.type(input, '  新知识库  ')
    await user.click(screen.getByRole('button', { name: '保存' }))

    expect(onConfirm).toHaveBeenCalledWith('新知识库')
  })

  it('rejects an empty name', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()

    render(
      <EditKnowledgeBaseDialog
        open
        currentName="原知识库"
        isPending={false}
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />,
    )

    await user.clear(screen.getByLabelText('名称'))
    await user.click(screen.getByRole('button', { name: '保存' }))

    expect(screen.getByText('请输入知识库名称。')).toBeInTheDocument()
    expect(onConfirm).not.toHaveBeenCalled()
  })
})
