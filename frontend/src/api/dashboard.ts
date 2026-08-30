import { apiRequest } from '../lib/apiClient'
import type { DashboardOverview } from '../types/dashboard'


export function getDashboardOverview(): Promise<DashboardOverview> {
  return apiRequest<DashboardOverview>('/dashboard/overview')
}
