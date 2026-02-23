export interface Session {
  id: string
  user_id: number
  username?: string
  gotty_url: string
  gotty_pid?: number
  gotty_port?: number
  status: 'starting' | 'running' | 'closed'
  started_at?: string
  last_activity_at?: string
  duration_seconds: number
}

export interface SessionListResponse {
  sessions: Session[]
  total: number
  limit: number
  offset: number
}

export interface StartSessionResponse {
  session_id: string
  gotty_url: string
  status: string
  started_at?: string
}
