import request from '@/utils/request'
import type { User } from '@/types/user'

export function getMe() {
  return request.get<{ success: boolean; data: User }>('/auth/me')
}

export function logout() {
  return request.post('/auth/logout')
}

export function getSamlLoginUrl() {
  return '/api/v1/auth/saml/login'
}

export function refresh() {
  return request.post<{ success: boolean; data: { expires_in: number } }>('/auth/refresh')
}

export function registerDevice(fingerprint: string) {
  return request.post('/auth/device/register', { fingerprint })
}
