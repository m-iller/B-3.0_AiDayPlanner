/**
 * Axios instance pre-configured for the AI Day Planner API.
 * All requests go to /api/v1/ — proxied to http://localhost:8000 in dev.
 */
import axios from 'axios'

export const http = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

/** Unwrap the ApiResponse envelope and return data, or throw on error. */
export async function call<T>(promise: Promise<{ data: { data: T; error: unknown } }>): Promise<T> {
  const res = await promise
  if (res.data.error) {
    const err = res.data.error as { code: string; message: string }
    throw new Error(`[${err.code}] ${err.message}`)
  }
  return res.data.data as T
}
