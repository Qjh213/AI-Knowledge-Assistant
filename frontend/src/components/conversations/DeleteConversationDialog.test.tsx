import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DeleteConversationDialog } from './DeleteConversationDialog'

describe('DeleteConversationDialog', () => {
  it('shows the target conversation and requires confirmation', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()

    render(
      <DeleteConversationDialog
        open
        conversationTitle="Milvus 使用问题"
        isPending={false}
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />,
    )

    expect(screen.getByText(/Milvus 使用问题/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '确认删除' }))
    expect(onConfirm).toHaveBeenCalledOnce()
  })

  it('does not render while closed', () => {
    const { container } = render(
      <DeleteConversationDialog
        open={false}
        conversationTitle="新对话"
        isPending={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    )

    expect(container).toBeEmptyDOMElement()
  })
})
