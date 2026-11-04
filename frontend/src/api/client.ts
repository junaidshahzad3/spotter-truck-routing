import { useMutation } from '@tanstack/react-query'
import type { ApiErrorBody, PlanRequest, PlanResponse } from './types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  readonly code: string
  readonly status: number

  constructor(message: string, code: string, status: number) {
    super(message)
    this.code = code
    this.status = status
  }

  /** Worth offering a retry? (upstream hiccups, timeouts, network, rate limit) */
  get retryable(): boolean {
    return this.status === 0 || this.status === 429 || this.status >= 500
  }
}

export async function postPlan(body: PlanRequest, signal?: AbortSignal): Promise<PlanResponse> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/api/plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err
    throw new ApiError('Could not reach the server. Check your connection.', 'network', 0)
  }
  if (!res.ok) {
    let message = `Request failed (HTTP ${res.status})`
    let code = 'http_error'
    try {
      const data = (await res.json()) as ApiErrorBody
      message = data.error?.message ?? message
      code = data.error?.code ?? code
    } catch {
      /* non-JSON error page */
    }
    throw new ApiError(message, code, res.status)
  }
  return (await res.json()) as PlanResponse
}

export function usePlan() {
  return useMutation<PlanResponse, ApiError, PlanRequest>({
    mutationKey: ['plan'],
    mutationFn: (body) => postPlan(body),
  })
}
