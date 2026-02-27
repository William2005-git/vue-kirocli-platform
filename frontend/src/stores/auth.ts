import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getMe, logout as apiLogout, refresh, registerDevice } from '@/api/auth'
import type { User } from '@/types/user'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const loading = ref(false)
  // JWT 过期时间（Unix 秒），从 Cookie 中解析
  const tokenExpiresAt = ref<number | null>(null)
  let proactiveRefreshTimer: ReturnType<typeof setTimeout> | null = null

  const isAuthenticated = computed(() => user.value !== null)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const permissions = computed(() => user.value?.permissions ?? {})

  /** 解析 JWT Cookie 中的 exp claim（不验证签名，仅读取 payload） */
  function parseTokenExpiry(): number | null {
    try {
      const cookies = document.cookie.split(';')
      const tokenCookie = cookies.find(c => c.trim().startsWith('access_token='))
      if (!tokenCookie) return null
      const token = tokenCookie.split('=')[1]?.trim()
      if (!token) return null
      const payload = JSON.parse(atob(token.split('.')[1]))
      return payload.exp ?? null
    } catch {
      return null
    }
  }

  /** 调度主动刷新：Token 剩余有效期不足 30 分钟时触发 */
  function scheduleProactiveRefresh() {
    if (proactiveRefreshTimer) clearTimeout(proactiveRefreshTimer)
    const exp = parseTokenExpiry()
    if (!exp) return
    tokenExpiresAt.value = exp
    const now = Math.floor(Date.now() / 1000)
    const remaining = exp - now
    // 剩余不足 30 分钟（1800 秒）时刷新，最少 10 秒后触发
    const delay = Math.max((remaining - 1800) * 1000, 10000)
    if (remaining > 0) {
      proactiveRefreshTimer = setTimeout(async () => {
        try {
          await refresh()
          scheduleProactiveRefresh()
        } catch {
          // 刷新失败由响应拦截器处理
        }
      }, delay)
    }
  }

  async function fetchCurrentUser() {
    loading.value = true
    try {
      const res = await getMe()
      user.value = res.data.data
      scheduleProactiveRefresh()
      // 登录后处理待注册的设备指纹（SAML 跨站 POST 无法携带 cookie，改由前端登录后主动上报）
      const pendingFp = localStorage.getItem('pending_device_fingerprint')
      if (pendingFp) {
        localStorage.removeItem('pending_device_fingerprint')
        registerDevice(pendingFp).catch(() => {/* 静默失败，不影响登录流程 */})
      }
    } catch {
      user.value = null
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    if (proactiveRefreshTimer) clearTimeout(proactiveRefreshTimer)
    try {
      await apiLogout()
    } finally {
      user.value = null
      window.location.href = '/login'
    }
  }

  return {
    user, loading, isAuthenticated, isAdmin, permissions, tokenExpiresAt,
    fetchCurrentUser, logout,
  }
})
