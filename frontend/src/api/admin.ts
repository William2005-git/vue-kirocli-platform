import request from '@/utils/request'

// ─── 类型定义 ─────────────────────────────────────────────────────────────────

export interface IPWhitelistEntry {
  id?: number
  cidr: string
  note?: string
}

export interface IPWhitelistData {
  enabled: boolean
  entries: IPWhitelistEntry[]
}

export interface AlertRule {
  id: number
  rule_key: string
  rule_name: string
  time_window_minutes: number
  threshold: number
  enabled: boolean
  updated_at: string | null
}

export interface AlertConfig {
  offhour_start: string
  offhour_end: string
  offhour_tz: string
  cooldown_minutes: number
  sns_topic_arn: string
}

export interface AlertEvent {
  id: number
  rule_key: string
  triggered_user_id: number | null
  triggered_username: string | null
  triggered_at: string | null
  event_detail: string | null
  notification_sent: boolean
  notification_error: string | null
}

export interface AuditLog {
  id: number
  event_type: string
  user_id: number | null
  username: string | null
  client_ip: string | null
  user_agent: string | null
  event_time: string | null
  event_detail: string | null
  result: string
}

// ─── IP 白名单 ─────────────────────────────────────────────────────────────────

export function getIPWhitelist() {
  return request.get<{ success: boolean; data: IPWhitelistData }>('/admin/ip-whitelist')
}

export function updateIPWhitelist(data: IPWhitelistData) {
  return request.put('/admin/ip-whitelist', data)
}

export function getMyIP() {
  return request.get<{ success: boolean; data: { ip: string } }>('/admin/ip-whitelist/my-ip')
}

// ─── 告警规则 ─────────────────────────────────────────────────────────────────

export function getAlertRules() {
  return request.get<{ success: boolean; data: { rules: AlertRule[]; config: AlertConfig } }>('/admin/alert-rules')
}

export function updateAlertRules(payload: { rules: Partial<AlertRule>[]; config: Partial<AlertConfig> }) {
  return request.put('/admin/alert-rules', payload)
}

export function testSNSAlert(sns_topic_arn: string) {
  return request.post('/admin/alert-rules/test-sns', { sns_topic_arn })
}

export function getAlertEvents(params?: {
  rule_key?: string
  start_time?: string
  end_time?: string
  limit?: number
  offset?: number
}) {
  return request.get<{ success: boolean; data: { events: AlertEvent[]; total: number } }>('/admin/alert-events', { params })
}

// ─── 审计日志 ─────────────────────────────────────────────────────────────────

export function getAuditLogs(params?: {
  user_id?: number
  event_type?: string
  start_time?: string
  end_time?: string
  limit?: number
  offset?: number
}) {
  return request.get<{ success: boolean; data: { logs: AuditLog[]; total: number } }>('/admin/audit-logs', { params })
}

export function exportAuditLogs(params?: {
  user_id?: number
  event_type?: string
  start_time?: string
  end_time?: string
}) {
  return request.get('/admin/audit-logs/export', { params, responseType: 'blob' })
}

// ─── 强制下线 ─────────────────────────────────────────────────────────────────

export function forceLogout(userId: number) {
  return request.post(`/admin/users/${userId}/force-logout`)
}

// ─── Secrets 状态 ─────────────────────────────────────────────────────────────

export function getSecretsStatus() {
  return request.get('/admin/secrets/status')
}
