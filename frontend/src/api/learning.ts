import { http, call } from './client'

export interface CorrectionCoefficient {
  task_id: string
  coefficient: number
  session_count: number
  updated_at: string
  reset_reason: string | null
}

export const learningApi = {
  get: (taskId: string) =>
    call<CorrectionCoefficient>(http.get(`/learning/${taskId}`)),

  reset: (taskId: string, reason: string) =>
    call<CorrectionCoefficient>(http.post(`/learning/${taskId}/reset`, { reason })),
}
