import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useToast } from '../../lib/toast'
import { ToastProvider } from './ToastProvider'


function ToastActions() {
  const { showToast } = useToast()

  return (
    <div>
      <button onClick={() => showToast('保存成功')}>显示成功提示</button>
      <button onClick={() => showToast('保存失败', 'error')}>
        显示错误提示
      </button>
    </div>
  )
}

function renderToasts() {
  return render(
    <ToastProvider>
      <ToastActions />
    </ToastProvider>,
  )
}

afterEach(() => {
  vi.useRealTimers()
})

describe('ToastProvider', () => {
  it('shows success and error notifications with accessible roles', async () => {
    const user = userEvent.setup()
    renderToasts()

    await user.click(screen.getByRole('button', { name: '显示成功提示' }))
    expect(screen.getByRole('status')).toHaveTextContent('保存成功')

    await user.click(screen.getByRole('button', { name: '显示错误提示' }))
    expect(screen.getByRole('alert')).toHaveTextContent('保存失败')
  })

  it('allows a notification to be dismissed manually', async () => {
    const user = userEvent.setup()
    renderToasts()

    await user.click(screen.getByRole('button', { name: '显示成功提示' }))
    await user.click(screen.getByRole('button', { name: '关闭提示' }))

    expect(screen.queryByText('保存成功')).not.toBeInTheDocument()
  })

  it('dismisses a notification automatically after four seconds', () => {
    vi.useFakeTimers()
    renderToasts()

    fireEvent.click(screen.getByRole('button', { name: '显示成功提示' }))
    expect(screen.getByText('保存成功')).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(4_000)
    })

    expect(screen.queryByText('保存成功')).not.toBeInTheDocument()
  })
})
