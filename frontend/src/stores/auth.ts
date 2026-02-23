import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getMe, logout as apiLogout } from '@/api/auth'
import type { User } from '@/types/user'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const loading = ref(false)

  const isAuthenticated = computed(() => user.value !== null)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const permissions = computed(() => user.value?.permissions ?? {})

  async function fetchCurrentUser() {
    loading.value = true
    try {
      const res = await getMe()
      user.value = res.data.data
    } catch {
      user.value = null
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    try {
      await apiLogout()
    } finally {
      user.value = null
      window.location.href = '/login'
    }
  }

  return { user, loading, isAuthenticated, isAdmin, permissions, fetchCurrentUser, logout }
})
