export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1'

let csrfToken = ''
let currentAccount = ''
export function setCsrfToken(value: string) { csrfToken = value }
export function setCurrentAccount(value: string) { currentAccount = value }
export function authenticatedHeaders(initial?: HeadersInit) {
  const headers = new Headers(initial)
  headers.set('X-Requested-With', 'KnowledgeAssistant')
  if (csrfToken) headers.set('X-CSRF-Token', csrfToken)
  if (currentAccount) headers.set('X-Account-ID', currentAccount)
  return headers
}
export function notifyAuthError(response: Response) {
  if (response.status === 401) window.dispatchEvent(new Event('auth-expired'))
  if (response.headers.get('X-Password-Change-Required') === 'true') window.dispatchEvent(new Event('password-required'))
}

interface ApiErrorBody {
  detail?: string
  code?: string
}

export class ApiError extends Error {
  readonly status: number
  readonly code?: string

  constructor(message: string, status: number, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = authenticatedHeaders(options.headers)

  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers.has('Content-Type')
  ) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    credentials: 'include',
    headers,
  })

  if (!response.ok) {
    if (!path.startsWith('/auth/')) notifyAuthError(response)
    let body: ApiErrorBody = {}

    try {
      body = (await response.json()) as ApiErrorBody
    } catch {
      // The server may return an empty or non-JSON error response.
    }

    throw new ApiError(
      body.detail ?? `请求失败（HTTP ${response.status}）`,
      response.status,
      body.code,
    )
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}
