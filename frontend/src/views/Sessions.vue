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
          {{ formatDuration(record.duration_seconds) }}
        </template>
        <template v-if="column.key === 'actions'">
          <a-space>
            <a-button
              v-if="record.status !== 'closed'"
              type="link"
              size="small"
              @click="openTerminal(record.gotty_url)"
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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { useSessionsStore } from '@/stores/sessions'
import { storeToRefs } from 'pinia'
import dayjs from 'dayjs'

const sessionsStore = useSessionsStore()
const { sessions, loading, total } = storeToRefs(sessionsStore)

const statusFilter = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const starting = ref(false)

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
  return t ? dayjs(t).format('YYYY-MM-DD HH:mm:ss') : '-'
}

function formatDuration(s: number) {
  const m = Math.floor(s / 60)
  return m > 0 ? `${m} 分钟` : `${s} 秒`
}

function openTerminal(url: string) {
  window.open(url, '_blank')
}

async function handleStart() {
  starting.value = true
  try {
    const data = await sessionsStore.startSession()
    message.success('终端启动成功')
    window.open(data.gotty_url, '_blank')
  } finally {
    starting.value = false
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

onMounted(() => loadSessions())
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
