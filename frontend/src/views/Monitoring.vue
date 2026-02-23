<template>
  <div>
    <div class="page-header">
      <h2>监控看板</h2>
      <a-space>
        <a-switch v-model:checked="autoRefresh" checked-children="自动刷新" un-checked-children="已暂停" @change="toggleAutoRefresh" />
        <a-button v-if="canExport" @click="handleExport">
          <template #icon><download-outlined /></template>
          导出 CSV
        </a-button>
      </a-space>
    </div>

    <a-row :gutter="16" class="metrics-row">
      <a-col :span="6">
        <a-card>
          <a-statistic title="活动会话数" :value="realtime?.active_sessions ?? 0" :value-style="{ color: '#3f8600' }">
            <template #prefix><code-outlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic title="在线用户数" :value="realtime?.online_users ?? 0">
            <template #prefix><user-outlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic title="CPU 使用率" :value="realtime?.cpu_usage_percent ?? 0" suffix="%" :precision="1"
            :value-style="{ color: (realtime?.cpu_usage_percent ?? 0) > 80 ? '#cf1322' : '#3f8600' }">
            <template #prefix><dashboard-outlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic title="内存使用率" :value="realtime?.memory_usage_percent ?? 0" suffix="%" :precision="1"
            :value-style="{ color: (realtime?.memory_usage_percent ?? 0) > 90 ? '#cf1322' : '#3f8600' }">
            <template #prefix><hdd-outlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="16">
      <a-col :span="24">
        <a-card title="统计分析">
          <template #extra>
            <a-radio-group v-model:value="days" @change="loadStats">
              <a-radio-button :value="7">7 天</a-radio-button>
              <a-radio-button :value="30">30 天</a-radio-button>
            </a-radio-group>
          </template>
          <a-spin :spinning="statsLoading">
            <a-row :gutter="16">
              <a-col :span="8">
                <a-statistic title="总用户数" :value="statistics?.total_users ?? 0" />
              </a-col>
              <a-col :span="8">
                <a-statistic title="总会话数" :value="statistics?.total_sessions ?? 0" />
              </a-col>
              <a-col :span="8">
                <a-statistic title="平均会话时长" :value="avgDuration" suffix="分钟" />
              </a-col>
            </a-row>
            <div ref="trendChartRef" style="height: 300px; margin-top: 24px"></div>
            <div ref="rankChartRef" style="height: 300px; margin-top: 24px"></div>
          </a-spin>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import { storeToRefs } from 'pinia'
import { useMonitoringStore } from '@/stores/monitoring'
import { useAuthStore } from '@/stores/auth'
import { exportReport } from '@/api/monitoring'
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import {
  CodeOutlined, UserOutlined, DashboardOutlined, HddOutlined, DownloadOutlined,
} from '@ant-design/icons-vue'

const monitoringStore = useMonitoringStore()
const authStore = useAuthStore()
const { realtime, statistics, loading: statsLoading } = storeToRefs(monitoringStore)
const canExport = computed(() => authStore.user?.permissions?.can_export_data)

const autoRefresh = ref(true)
const days = ref(7)
const trendChartRef = ref<HTMLElement>()
const rankChartRef = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null
let rankChart: echarts.ECharts | null = null

const avgDuration = computed(() =>
  Math.round((statistics.value?.average_session_duration_seconds as number ?? 0) / 60)
)

function toggleAutoRefresh(val: boolean) {
  if (val) monitoringStore.startAutoRefresh()
  else monitoringStore.stopAutoRefresh()
}

async function loadStats() {
  await monitoringStore.fetchStatistics(days.value)
  renderCharts()
}

function renderCharts() {
  const stats = statistics.value as Record<string, unknown>
  if (!stats) return

  if (trendChartRef.value) {
    if (!trendChart) trendChart = echarts.init(trendChartRef.value)
    const daily = (stats.daily_sessions as { date: string; count: number }[]) || []
    trendChart.setOption({
      title: { text: '每日会话数趋势' },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: daily.map((d) => d.date) },
      yAxis: { type: 'value' },
      series: [{ data: daily.map((d) => d.count), type: 'line', smooth: true, areaStyle: {} }],
    })
  }

  if (rankChartRef.value) {
    if (!rankChart) rankChart = echarts.init(rankChartRef.value)
    const top = (stats.top_users as { username: string; session_count: number }[]) || []
    rankChart.setOption({
      title: { text: '用户使用排行 Top 10' },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: top.map((u) => u.username) },
      yAxis: { type: 'value' },
      series: [{ data: top.map((u) => u.session_count), type: 'bar' }],
    })
  }
}

async function handleExport() {
  try {
    const end = dayjs().format('YYYY-MM-DD')
    const start = dayjs().subtract(days.value, 'day').format('YYYY-MM-DD')
    const res = await exportReport(start, end)
    const url = URL.createObjectURL(new Blob([res.data as BlobPart]))
    const a = document.createElement('a')
    a.href = url
    a.download = `sessions_${start}_${end}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    message.error('导出失败')
  }
}

onMounted(async () => {
  await monitoringStore.fetchRealtime()
  await loadStats()
  if (autoRefresh.value) monitoringStore.startAutoRefresh()
})

onUnmounted(() => {
  monitoringStore.stopAutoRefresh()
  trendChart?.dispose()
  rankChart?.dispose()
})

watch(statistics, () => renderCharts())
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}
.page-header h2 { margin: 0; }
.metrics-row { margin-bottom: 24px; }
</style>
