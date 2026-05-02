import { http, call } from './client'

export interface TimeBlock {
  id: string
  day_of_week: number
  start_time: string
  end_time: string
  label: string
  is_recurring: boolean
  week_number: number | null
  year: number | null
}

export interface TimeBlockCreateRequest {
  day_of_week: number
  start_time: string
  end_time: string
  label: string
  is_recurring?: boolean
  week_number?: number | null
  year?: number | null
}

export interface FreeSlot {
  date: string
  start_time: string
  end_time: string
  duration_minutes: number
}

export interface ScheduleEntry {
  id: string
  task_id: string
  scheduled_date: string
  slot_start: string
  slot_end: string
  is_confirmed: boolean
}

export interface WeeklyView {
  week_number: number
  year: number
  time_blocks: TimeBlock[]
  schedule_entries: ScheduleEntry[]
  free_slots: Record<string, FreeSlot[]>
}

export const calendarApi = {
  getWeek: (week: number, year: number) =>
    call<WeeklyView>(http.get('/calendar/week', { params: { week_number: week, year } })),

  createBlock: (data: TimeBlockCreateRequest) =>
    call<TimeBlock>(http.post('/calendar/blocks', data)),

  getBlock: (id: string) =>
    call<TimeBlock>(http.get(`/calendar/blocks/${id}`)),

  deleteBlock: (id: string) =>
    call<null>(http.delete(`/calendar/blocks/${id}`)),
}
