export interface Permission {
  max_concurrent_sessions: number
  max_session_duration_hours: number
  daily_session_quota: number
  can_start_terminal: boolean
  can_view_monitoring: boolean
  can_export_data: boolean
}

export interface Preference {
  language: string
  theme: string
  timezone: string
}

export interface User {
  id: number
  username: string
  email: string
  full_name?: string
  role: 'admin' | 'user'
  status: 'active' | 'disabled'
  groups: string[]
  permissions?: Permission
  preferences?: Preference
  last_login_at?: string
  created_at?: string
}
