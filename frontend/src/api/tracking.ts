import { http, call } from './client'

export interface Interruption {
  id: string
  session_id: string
  start_time: string
  end_time: string | null
  duration_minutes: number | null
}

export interface TrackingSession {
  id: string
  task_id: string
  start_time: string
  end_time: string | null
  actual_duration: number | null
  interruptions: Interruption[]
  created_at: string
}

export const trackingApi = {
  start: (taskId: string) =>
    call<TrackingSession>(http.post('/tracking/start', { task_id: taskId })),

  stop: (taskId: string) =>
    call<TrackingSession>(http.post('/tracking/stop', { task_id: taskId })),

  interruptStart: (taskId: string) =>
    call<Interruption>(http.post('/tracking/interrupt/start', { task_id: taskId })),

  interruptEnd: (taskId: string) =>
    call<Interruption>(http.post('/tracking/interrupt/end', { task_id: taskId })),

  getSessions: (taskId: string) =>
    call<TrackingSession[]>(http.get(`/tracking/${taskId}`)),
}
