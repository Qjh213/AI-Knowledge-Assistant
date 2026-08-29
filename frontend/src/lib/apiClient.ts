const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1'

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
  const headers = new Headers(options.headers)

  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers.has('Content-Type')
  ) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
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
