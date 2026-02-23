import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getSessions, startSession as apiStart, closeSession as apiClose } from '@/api/sessions'
import type { Session } from '@/types/session'

export const useSessionsStore = defineStore('sessions', () => {
  const sessions = ref<Session[]>([])
  const loading = ref(false)
  const total = ref(0)
  let refreshTimer: ReturnType<typeof setInterval> | null = null

  const activeSessions = computed(() =>
    sessions.value.filter((s) => s.status === 'running' || s.status === 'starting')
  )

  async function fetchSessions(params?: { status?: string; limit?: number; offset?: number }) {
    loading.value = true
    try {
      const res = await getSessions(params)
      sessions.value = res.data.data.sessions
      total.value = res.data.data.total
    } finally {
      loading.value = false
    }
  }

  async function startSession() {
    const res = await apiStart()
    await fetchSessions()
    return res.data.data
  }

  async function closeSession(sessionId: string) {
    await apiClose(sessionId)
    await fetchSessions()
  }

  function startAutoRefresh(interval = 5000) {
    stopAutoRefresh()
    refreshTimer = setInterval(() => fetchSessions(), interval)
  }

  function stopAutoRefresh() {
    if (refreshTimer !== null) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
  }

  return {
    sessions,
    loading,
    total,
    activeSessions,
    fetchSessions,
    startSession,
    closeSession,
    startAutoRefresh,
    stopAutoRefresh,
  }
})
