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
