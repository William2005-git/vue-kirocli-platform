<template>
  <div>
    <div class="welcome-section">
      <div>
        <h2>欢迎回来，{{ user?.full_name || user?.username }}</h2>
        <p>您当前有 {{ activeSessions.length }} 个活动会话（最多 {{ maxSessions }} 个）</p>
      </div>
      <a-button
        type="primary"
        size="large"
        :loading="starting"
        :disabled="activeSessions.length >= maxSessions"
        @click="handleStartSession"
      >
        <template #icon><plus-outlined /></template>
        启动新终端
      </a-button>
    </div>

    <a-row :gutter="16" class="metrics-row">
      <a-col :span="6">
        <a-card>
          <a-statistic title="活动会话数" :value="activeSessions.length" :value-style="{ color: '#3f8600' }">
            <template #prefix><code-outlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic title="今日使用时长" :value="todayDuration" suffix="分钟">
            <template #prefix><clock-circle-outlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic title="总会话数" :value="totalSessions">
            <template #prefix><history-outlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic title="今日剩余配额" :value="remainingQuota" :value-style="{ color: remainingQuota > 0 ? '#3f8600' : '#cf1322' }">
            <template #prefix><fund-outlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
    </a-row>

    <a-card class="sessions-card">
      <template #title>
        <span>我的活动会话</span>
      </template>
      <template #extra>
        <a-button size="small" @click="sessionsStore.fetchSessions()">
          <template #icon><reload-outlined /></template>
          刷新
        </a-button>
      </template>

      <a-spin :spinning="loading">
        <div v-if="activeSessions.length === 0" class="empty-state">
          <a-empty description="您还没有启动任何会话">
            <a-button type="primary" @click="handleStartSession">启动新终端</a-button>
          </a-empty>
        </div>
        <a-row v-else :gutter="16">
          <a-col v-for="sess in activeSessions" :key="sess.id" :span="8">
            <a-card class="session-card" size="small">
              <div class="session-header">
                <a-badge :status="sess.status === 'running' ? 'success' : 'processing'" />
                <span class="session-id">{{ sess.id }}</span>
                <a-tag :color="sess.status === 'running' ? 'green' : 'orange'">
                  {{ sess.status === 'running' ? '运行中' : '启动中' }}
                </a-tag>
              </div>
              <div class="session-info">
                <div>启动时间：{{ formatTime(sess.started_at) }}</div>
                <div>持续时长：{{ formatLiveDuration(sess) }}</div>
                <div v-if="isAdmin && sess.username">用户：{{ sess.username }}</div>
              </div>
              <div class="session-actions">
                <a-button type="primary" size="small" @click="openTerminal(sess.random_token)">
                  打开终端
                </a-button>
                <a-button danger size="small" @click="confirmClose(sess.id)">
                  中止会话
                </a-button>
              </div>
            </a-card>
          </a-col>
        </a-row>
      </a-spin>
    </a-card>

    <a-modal
      v-model:open="closeModalVisible"
      title="确认中止会话"
      ok-text="确认中止"
      cancel-text="取消"
      ok-type="danger"
      :confirm-loading="closing"
      @ok="handleCloseSession"
    >
      <p>确定要中止会话 <strong>{{ closingSessionId }}</strong> 吗？此操作不可撤销。</p>
    </a-modal>

    <a-modal
      v-model:open="startingModalVisible"
      title="正在启动终端"
      :footer="null"
      :closable="false"
      :maskClosable="false"
    >
      <div style="text-align: center; padding: 20px 0;">
        <a-progress :percent="startingProgress" status="active" />
        <p style="margin-top: 16px; color: #666;">{{ startingMessage }}</p>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { useSessionsStore } from '@/stores/sessions'
import {
  PlusOutlined, CodeOutlined, ClockCircleOutlined,
  HistoryOutlined, FundOutlined, ReloadOutlined,
} from '@ant-design/icons-vue'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import utc from 'dayjs/plugin/utc'
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.extend(utc)
dayjs.locale('zh-cn')

const authStore = useAuthStore()
const sessionsStore = useSessionsStore()
const { user } = storeToRefs(authStore)
const { activeSessions, loading, sessions } = storeToRefs(sessionsStore)
const isAdmin = authStore.isAdmin

const starting = ref(false)
const closeModalVisible = ref(false)
const closingSessionId = ref('')
const closing = ref(false)
const startingModalVisible = ref(false)
const startingProgress = ref(0)
const startingMessage = ref('正在创建会话...')
const currentTime = ref(Date.now()) // 用于实时更新持续时长

const maxSessions = computed(() => user.value?.permissions?.max_concurrent_sessions ?? 3)
const dailyQuota = computed(() => user.value?.permissions?.daily_session_quota ?? 10)

const todayDuration = computed(() => {
  const today = dayjs().startOf('day')
  return Math.round(
    sessions.value
      .filter((s) => dayjs(s.started_at).isAfter(today))
      .reduce((sum, s) => sum + s.duration_seconds, 0) / 60
  )
})

const totalSessions = computed(() => sessions.value.length)

const remainingQuota = computed(() => {
  const today = dayjs().startOf('day')
  const todayCount = sessions.value.filter((s) => dayjs(s.started_at).isAfter(today)).length
  return Math.max(0, dailyQuota.value - todayCount)
})

async function handleStartSession() {
  starting.value = true
  startingModalVisible.value = true
  startingProgress.value = 0
  startingMessage.value = '正在创建会话...'
  
  try {
    // 阶段 1: 创建会话 (0% → 30%)
    const data = await sessionsStore.startSession()
    startingProgress.value = 30
    startingMessage.value = '会话已创建，正在启动终端...'
    
    // 阶段 2: 等待 Gotty 启动 (30% → 60%)
    await new Promise(resolve => setTimeout(resolve, 1000))
    startingProgress.value = 60
    startingMessage.value = '正在配置终端环境...'
    
    // 阶段 3: 轮询检查会话状态 (60% → 80%)
    const sessionId = data.session_id
    let attempts = 0
    const maxAttempts = 10
    
    while (attempts < maxAttempts) {
      await new Promise(resolve => setTimeout(resolve, 500))
      await sessionsStore.fetchSessions()
      
      const session = sessions.value.find(s => s.id === sessionId)
      if (session?.status === 'running') {
        startingProgress.value = 80
        startingMessage.value = '终端已启动，正在配置路由...'
        break
      }
      
      attempts++
      startingProgress.value = 60 + (attempts * 2)
    }
    
    // 阶段 4: 等待 Nginx 配置更新 (80% → 95%)
    // 确保 Nginx 路由配置已更新（后端在会话创建后 3 秒更新）
    await new Promise(resolve => setTimeout(resolve, 2000))
    startingProgress.value = 95
    startingMessage.value = '路由配置完成，准备打开终端...'
    
    // 阶段 5: 完成 (95% → 100%)
    await new Promise(resolve => setTimeout(resolve, 500))
    startingProgress.value = 100
    startingMessage.value = '启动成功！'
    
    await new Promise(resolve => setTimeout(resolve, 300))
    
    // 打开终端窗口
    window.open(`/terminal/${data.random_token}/`, '_blank')
    message.success('终端启动成功')
    
  } catch (error) {
    // 错误已由 interceptor 处理
  } finally {
    starting.value = false
    startingModalVisible.value = false
    startingProgress.value = 0
  }
}

function openTerminal(token: string) {
  window.open(`/terminal/${token}/`, '_blank')
}

function confirmClose(sessionId: string) {
  closingSessionId.value = sessionId
  closeModalVisible.value = true
}

async function handleCloseSession() {
  closing.value = true
  try {
    await sessionsStore.closeSession(closingSessionId.value)
    message.success('会话已中止')
    closeModalVisible.value = false
  } finally {
    closing.value = false
  }
}

function formatTime(t?: string) {
  // 后端返回的是 UTC 时间，需要明确指定为 UTC
  return t ? dayjs.utc(t).local().fromNow() : '-'
}

function formatDuration(seconds: number) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m} 分 ${s} 秒`
}

function formatLiveDuration(sess: any) {
  if (!sess.started_at) return '-'
  
  // 如果会话已关闭，使用后端返回的 duration_seconds
  if (sess.status === 'closed') {
    return formatDuration(sess.duration_seconds)
  }
  
  // 如果会话运行中，实时计算持续时长
  // 后端返回的是 UTC 时间，需要明确指定为 UTC
  const startTime = dayjs.utc(sess.started_at)
  const now = dayjs(currentTime.value)
  const seconds = Math.floor(now.diff(startTime, 'second'))
  
  return formatDuration(seconds)
}

onMounted(() => {
  sessionsStore.fetchSessions()
  sessionsStore.startAutoRefresh(5000)
  
  // 每秒更新一次当前时间，用于实时显示持续时长
  const timer = setInterval(() => {
    currentTime.value = Date.now()
  }, 1000)
  
  // 保存 timer ID 以便在 unmount 时清理
  ;(window as any).__dashboardTimer = timer
})

onUnmounted(() => {
  sessionsStore.stopAutoRefresh()
  
  // 清理定时器
  if ((window as any).__dashboardTimer) {
    clearInterval((window as any).__dashboardTimer)
    delete (window as any).__dashboardTimer
  }
})
</script>

<style scoped>
.welcome-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}
.welcome-section h2 { margin: 0; font-size: 22px; }
.welcome-section p { margin: 4px 0 0; color: #666; }
.metrics-row { margin-bottom: 24px; }
.sessions-card { margin-top: 8px; }
.empty-state { padding: 40px 0; }
.session-card { margin-bottom: 16px; }
.session-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.session-id { font-family: monospace; font-size: 12px; flex: 1; }
.session-info { font-size: 13px; color: #666; margin-bottom: 12px; line-height: 1.8; }
.session-actions { display: flex; gap: 8px; }
</style>
