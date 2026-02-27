<template>
  <div>
    <div class="page-header">
      <h2>终端会话管理</h2>
      <a-space>
        <a-select v-model:value="statusFilter" style="width: 120px" @change="handleFilter">
          <a-select-option value="">全部</a-select-option>
          <a-select-option value="running">运行中</a-select-option>
          <a-select-option value="starting">启动中</a-select-option>
          <a-select-option value="closed">已关闭</a-select-option>
        </a-select>
        <a-button type="primary" :loading="starting" @click="handleStart">
          <template #icon><plus-outlined /></template>
          启动新终端
        </a-button>
      </a-space>
    </div>

    <a-table
      :columns="columns"
      :data-source="sessions"
      :loading="loading"
      :pagination="{ total, pageSize: pageSize, current: currentPage, onChange: handlePageChange }"
      row-key="id"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-badge
            :status="record.status === 'running' ? 'success' : record.status === 'starting' ? 'processing' : 'default'"
            :text="statusText(record.status)"
          />
        </template>
        <template v-if="column.key === 'started_at'">
          {{ formatDate(record.started_at) }}
        </template>
        <template v-if="column.key === 'duration'">
          {{ formatLiveDuration(record) }}
        </template>
        <template v-if="column.key === 'actions'">
          <a-space>
            <a-button
              v-if="record.status !== 'closed'"
              type="link"
              size="small"
              @click="openTerminal(record.random_token)"
            >打开</a-button>
            <a-popconfirm
              v-if="record.status !== 'closed'"
              title="确认关闭此会话？"
              ok-text="确认"
              cancel-text="取消"
              @confirm="handleClose(record.id)"
            >
              <a-button type="link" danger size="small">关闭</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

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
import { ref, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { useSessionsStore } from '@/stores/sessions'
import { storeToRefs } from 'pinia'
import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'

dayjs.extend(utc)

const sessionsStore = useSessionsStore()
const { sessions, loading, total } = storeToRefs(sessionsStore)

const statusFilter = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const starting = ref(false)
const startingModalVisible = ref(false)
const startingProgress = ref(0)
const startingMessage = ref('正在创建会话...')
const currentTime = ref(Date.now()) // 用于实时更新持续时长

const columns = [
  { title: '会话 ID', dataIndex: 'id', key: 'id', ellipsis: true },
  { title: '用户', dataIndex: 'username', key: 'username' },
  { title: '状态', key: 'status' },
  { title: '启动时间', key: 'started_at' },
  { title: '持续时长', key: 'duration' },
  { title: '操作', key: 'actions' },
]

function statusText(s: string) {
  return { running: '运行中', starting: '启动中', closed: '已关闭' }[s] || s
}

function formatDate(t?: string) {
  // 后端返回的是 UTC 时间，转换为本地时间显示
  return t ? dayjs.utc(t).local().format('YYYY-MM-DD HH:mm:ss') : '-'
}

function formatDuration(s: number) {
  const m = Math.floor(s / 60)
  return m > 0 ? `${m} 分钟` : `${s} 秒`
}

function formatLiveDuration(record: any) {
  if (!record.started_at) return '-'
  
  // 如果会话已关闭，使用后端返回的 duration_seconds
  if (record.status === 'closed') {
    return formatDuration(record.duration_seconds)
  }
  
  // 如果会话运行中，实时计算持续时长
  // 后端返回的是 UTC 时间，需要明确指定为 UTC
  const startTime = dayjs.utc(record.started_at)
  const now = dayjs(currentTime.value)
  const seconds = Math.floor(now.diff(startTime, 'second'))
  
  return formatDuration(seconds)
}

function openTerminal(token: string) {
  window.open(`/terminal/${token}/`, '_blank')
}

async function handleStart() {
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

async function handleClose(id: string) {
  await sessionsStore.closeSession(id)
  message.success('会话已关闭')
}

function handleFilter() {
  currentPage.value = 1
  loadSessions()
}

function handlePageChange(page: number) {
  currentPage.value = page
  loadSessions()
}

function loadSessions() {
  sessionsStore.fetchSessions({
    status: statusFilter.value || undefined,
    limit: pageSize.value,
    offset: (currentPage.value - 1) * pageSize.value,
  })
}

onMounted(() => {
  loadSessions()
  
  // 每秒更新一次当前时间，用于实时显示持续时长
  const timer = setInterval(() => {
    currentTime.value = Date.now()
  }, 1000)
  
  // 保存 timer ID 以便在 unmount 时清理
  ;(window as any).__sessionsTimer = timer
})

// 添加 onUnmounted 钩子清理定时器
onUnmounted(() => {
  if ((window as any).__sessionsTimer) {
    clearInterval((window as any).__sessionsTimer)
    delete (window as any).__sessionsTimer
  }
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}
.page-header h2 { margin: 0; }
</style>
