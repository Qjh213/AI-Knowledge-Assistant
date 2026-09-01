import { API_BASE_URL } from '../lib/apiClient'

export type ServiceConnectionState = 'healthy' | 'degraded' | 'offline'

export interface ServiceConnection {
  state: ServiceConnectionState
  label: string
}

export async function getServiceConnection(): Promise<ServiceConnection> {
  try {
    const response = await fetch(`${API_BASE_URL}/health/ready`)

    if (response.ok) {
      return { state: 'healthy', label: '服务运行正常' }
    }

    return { state: 'degraded', label: '部分服务暂不可用' }
  } catch {
    return { state: 'offline', label: '暂时无法连接服务' }
  }
}
