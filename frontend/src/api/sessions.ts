import request from '@/utils/request'
import type { Session, SessionListResponse, StartSessionResponse } from '@/types/session'

export function startSession() {
  return request.post<{ success: boolean; data: StartSessionResponse }>('/sessions/start')
}

export function getSessions(params?: {
  status?: string
  user_id?: number
  limit?: number
  offset?: number
}) {
  return request.get<{ success: boolean; data: SessionListResponse }>('/sessions', { params })
}

export function getSession(sessionId: string) {
  return request.get<{ success: boolean; data: Session }>(`/sessions/${sessionId}`)
}

export function closeSession(sessionId: string) {
  return request.delete(`/sessions/${sessionId}`)
}
