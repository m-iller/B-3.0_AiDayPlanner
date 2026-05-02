import { http, call } from './client'
import type { FreeSlot } from './calendar'

export interface ScheduleDecision {
  task_id: string
  outcome: 'assigned' | 'skipped' | 'deferred'
  slot: FreeSlot | null
  priority_score: number
  fatigue_score: number
  completion_probability: number | null
  reason: string
}

export interface ScheduleResult {
  assigned: ScheduleDecision[]
  skipped: ScheduleDecision[]
  deferred: ScheduleDecision[]
}

export const schedulerApi = {
  run: (date: string, dryRun = false) =>
    call<ScheduleResult>(
      http.post('/schedule/run', { date }, { params: { dry_run: dryRun } })
    ),

  confirm: (entryId: string) =>
    call<{ id: string; is_confirmed: boolean }>(
      http.post(`/schedule/confirm/${entryId}`)
    ),
}
