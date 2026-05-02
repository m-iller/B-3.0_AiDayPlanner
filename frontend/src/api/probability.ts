import { http, call } from './client'

export interface CompletionProbability {
  task_id: string
  slot_date: string
  slot_start: string
  probability: number
}

export interface DayAggregate {
  date: string
  aggregate_probability: number
  overload_warning: boolean
  task_probabilities: CompletionProbability[]
}

export const probabilityApi = {
  forTask: (taskId: string, slotDate: string, slotStart: string) =>
    call<CompletionProbability>(
      http.get('/probability/task', {
        params: { task_id: taskId, slot_date: slotDate, slot_start: slotStart },
      })
    ),

  forDay: (date: string) =>
    call<DayAggregate>(http.get(`/probability/day/${date}`)),
}
