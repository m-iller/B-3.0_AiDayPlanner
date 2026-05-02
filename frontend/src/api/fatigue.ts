import { http, call } from './client'

export interface FatigueRecord {
  id: string
  record_date: string
  score: number
  updated_at: string
}

export interface FatigueAuditEntry {
  id: string
  record_date: string
  old_score: number
  new_score: number
  cause: string
  cause_detail: unknown
  override_reason: string | null
  created_at: string
}

export const fatigueApi = {
  getForDate: (date: string) =>
    call<{ record: FatigueRecord; audit_log: FatigueAuditEntry[] }>(
      http.get(`/fatigue/${date}`)
    ),

  override: (date: string, score: number, reason: string) =>
    call<FatigueRecord>(
      http.post('/fatigue/override', { date, score, reason })
    ),
}
