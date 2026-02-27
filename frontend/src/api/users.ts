import request from '@/utils/request'

export function getAdminUsers(params?: {
  role?: string
  status?: string
  search?: string
  limit?: number
  offset?: number
}) {
  return request.get('/admin/users', { params })
}

export function getAdminUser(userId: number) {
  return request.get(`/admin/users/${userId}`)
}

export function updateUserPermissions(userId: number, permissions: Record<string, unknown>) {
  return request.put(`/admin/users/${userId}/permissions`, permissions)
}

export function syncUsers() {
  return request.post('/admin/users/sync')
}

export function getGroups() {
  return request.get('/admin/groups')
}

export function updateGroupRole(groupId: number, role: string) {
  return request.put(`/admin/groups/${groupId}/role`, { role })
}

export function getMyPreferences() {
  return request.get('/users/me/preferences')
}

export function updateMyPreferences(prefs: Record<string, string>) {
  return request.put('/users/me/preferences', prefs)
}

// ─── 设备管理 ─────────────────────────────────────────────────────────────────

export interface UserDevice {
  id: number
  device_name: string
  fingerprint_preview: string
  first_seen_at: string
  last_seen_at: string
  last_seen_ip: string | null
  login_count: number
  is_current: boolean
}

export function getMyDevices() {
  return request.get<{ success: boolean; data: { devices: UserDevice[] } }>('/users/me/devices')
}

export function updateMyDevice(deviceId: number, data: { device_name: string }) {
  return request.put(`/users/me/devices/${deviceId}`, data)
}

export function deleteMyDevice(deviceId: number) {
  return request.delete(`/users/me/devices/${deviceId}`)
}
