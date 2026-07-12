import type { ApiErrorBody } from '../types/api'
import { getAccessToken, notifyUnauthorized } from '../stores/auth-token'

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message) }
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers)
  const token = getAccessToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers })
  if (response.status === 401) notifyUnauthorized()
  if (!response.ok) {
    let body: ApiErrorBody = {}
    try { body = await response.json() as ApiErrorBody } catch { /* safe fallback */ }
    throw new ApiError(
      response.status,
      body.error?.code || 'request_failed',
      body.error?.message || 'The request could not be completed.',
    )
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export function safeError(error: unknown) {
  return error instanceof ApiError ? error.message : 'Something went wrong. Please try again.'
}
