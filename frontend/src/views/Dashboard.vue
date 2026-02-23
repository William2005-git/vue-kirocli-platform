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
                <div>持续时长：{{ formatDuration(sess.duration_seconds) }}</div>
                <div v-if="isAdmin && sess.username">用户：{{ sess.username }}</div>
              </div>
              <div class="session-actions">
                <a-button type="primary" size="small" @click="openTerminal(sess.gotty_url)">
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
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
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
  try {
    const data = await sessionsStore.startSession()
    message.success('终端启动成功')
    window.open(data.gotty_url, '_blank')
  } catch {
    // error handled by interceptor
  } finally {
    starting.value = false
  }
}

function openTerminal(url: string) {
  window.open(url, '_blank')
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
  return t ? dayjs(t).fromNow() : '-'
}

function formatDuration(seconds: number) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m} 分 ${s} 秒`
}

onMounted(() => {
  sessionsStore.fetchSessions()
  sessionsStore.startAutoRefresh(5000)
})

onUnmounted(() => {
  sessionsStore.stopAutoRefresh()
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
