import { http, call } from './client'

export interface Task {
  id: string
  title: string
  description: string
  difficulty: number
  urgency: number
  importance: number
  estimated_duration: number
  task_type: 'one_time' | 'recurring' | 'no_date'
  state: 'pending' | 'in_progress' | 'interrupted' | 'completed'
  recurrence_rule: { interval: number; unit: string } | null
  dependency_ids: string[]
  created_at: string
  updated_at: string
}

export interface TaskCreateRequest {
  title: string
  description?: string
  difficulty: number
  urgency: number
  importance: number
  estimated_duration: number
  task_type: 'one_time' | 'recurring' | 'no_date'
  dependency_ids?: string[]
  recurrence_rule?: { interval: number; unit: string } | null
}

export interface TaskQueryFilters {
  task_type?: string
  difficulty_min?: number
  difficulty_max?: number
  urgency_min?: number
  urgency_max?: number
  importance_min?: number
  importance_max?: number
  scheduled?: boolean
}

export const tasksApi = {
  list: (filters?: TaskQueryFilters) =>
    call<Task[]>(http.get('/tasks', { params: filters })),

  get: (id: string) =>
    call<Task>(http.get(`/tasks/${id}`)),

  create: (data: TaskCreateRequest) =>
    call<Task>(http.post('/tasks', data)),

  update: (id: string, data: Partial<TaskCreateRequest>) =>
    call<Task>(http.patch(`/tasks/${id}`, data)),

  delete: (id: string) =>
    call<null>(http.delete(`/tasks/${id}`)),
}
