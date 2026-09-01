import { afterEach, describe, expect, it, vi } from 'vitest'
import { getServiceConnection } from './health'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('getServiceConnection', () => {
  it('reports a healthy service', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}')))
    await expect(getServiceConnection()).resolves.toEqual({
      state: 'healthy',
      label: '服务运行正常',
    })
  })

  it('reports degraded dependencies', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('{}', { status: 503 })),
    )
    await expect(getServiceConnection()).resolves.toEqual({
      state: 'degraded',
      label: '部分服务暂不可用',
    })
  })

  it('reports an offline backend', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    await expect(getServiceConnection()).resolves.toEqual({
      state: 'offline',
      label: '暂时无法连接服务',
    })
  })
})
