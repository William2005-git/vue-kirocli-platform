import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getRealtimeMetrics, getStatistics } from '@/api/monitoring'

export const useMonitoringStore = defineStore('monitoring', () => {
  const realtime = ref<Record<string, unknown> | null>(null)
  const statistics = ref<Record<string, unknown> | null>(null)
  const loading = ref(false)
  let refreshTimer: ReturnType<typeof setInterval> | null = null

  async function fetchRealtime() {
    try {
      const res = await getRealtimeMetrics()
      realtime.value = (res.data as { data: Record<string, unknown> }).data
    } catch {
      // ignore
    }
  }

  async function fetchStatistics(days = 7) {
    loading.value = true
    try {
      const res = await getStatistics(days)
      statistics.value = (res.data as { data: Record<string, unknown> }).data
    } finally {
      loading.value = false
    }
  }

  function startAutoRefresh(interval = 5000) {
    stopAutoRefresh()
    refreshTimer = setInterval(() => fetchRealtime(), interval)
  }

  function stopAutoRefresh() {
    if (refreshTimer !== null) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
  }

  return { realtime, statistics, loading, fetchRealtime, fetchStatistics, startAutoRefresh, stopAutoRefresh }
})
