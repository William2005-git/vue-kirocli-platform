<template>
  <div>
    <div class="page-header">
      <h2>用户管理</h2>
      <a-button type="primary" :loading="syncing" @click="handleSync">
        <template #icon><sync-outlined /></template>
        从 IAM Identity Center 同步用户
      </a-button>
    </div>

    <a-card style="margin-bottom: 16px">
      <a-space>
        <a-input-search
          v-model:value="search"
          placeholder="搜索用户名或邮箱"
          style="width: 240px"
          @search="loadUsers"
        />
        <a-select v-model:value="roleFilter" style="width: 120px" @change="loadUsers">
          <a-select-option value="">全部角色</a-select-option>
          <a-select-option value="admin">管理员</a-select-option>
          <a-select-option value="user">普通用户</a-select-option>
        </a-select>
        <a-select v-model:value="statusFilter" style="width: 120px" @change="loadUsers">
          <a-select-option value="">全部状态</a-select-option>
          <a-select-option value="active">活跃</a-select-option>
          <a-select-option value="disabled">已禁用</a-select-option>
        </a-select>
      </a-space>
    </a-card>

    <a-table
      :columns="columns"
      :data-source="users"
      :loading="loading"
      :pagination="{ total, pageSize: 20, current: currentPage, onChange: handlePageChange }"
      row-key="id"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'role'">
          <a-tag :color="record.role === 'admin' ? 'red' : 'blue'">
            {{ record.role === 'admin' ? '管理员' : '普通用户' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'status'">
          <a-badge :status="record.status === 'active' ? 'success' : 'error'" :text="record.status === 'active' ? '活跃' : '已禁用'" />
        </template>
        <template v-if="column.key === 'last_login_at'">
          {{ record.last_login_at ? dayjs(record.last_login_at).format('YYYY-MM-DD HH:mm') : '从未' }}
        </template>
        <template v-if="column.key === 'actions'">
          <a-space>
            <a-button type="link" size="small" @click="openPermissions(record)">配置权限</a-button>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="permModalVisible"
      :title="`配置权限 - ${selectedUser?.username}`"
      ok-text="保存"
      cancel-text="取消"
      :confirm-loading="saving"
      @ok="savePermissions"
    >
      <a-form :model="permForm" layout="vertical">
        <a-form-item label="最大并发会话数">
          <a-input-number v-model:value="permForm.max_concurrent_sessions" :min="1" :max="10" style="width: 100%" />
        </a-form-item>
        <a-form-item label="单次会话最长时长（小时）">
          <a-input-number v-model:value="permForm.max_session_duration_hours" :min="1" :max="8" style="width: 100%" />
        </a-form-item>
        <a-form-item label="每日会话配额">
          <a-input-number v-model:value="permForm.daily_session_quota" :min="1" :max="50" style="width: 100%" />
        </a-form-item>
        <a-form-item label="功能权限">
          <a-space direction="vertical">
            <a-switch v-model:checked="permForm.can_start_terminal" checked-children="允许" un-checked-children="禁止" />
            <span>允许启动终端</span>
            <a-switch v-model:checked="permForm.can_view_monitoring" checked-children="允许" un-checked-children="禁止" />
            <span>允许查看监控</span>
            <a-switch v-model:checked="permForm.can_export_data" checked-children="允许" un-checked-children="禁止" />
            <span>允许导出数据</span>
          </a-space>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { SyncOutlined } from '@ant-design/icons-vue'
import { getAdminUsers, syncUsers, getAdminUser, updateUserPermissions } from '@/api/users'
import dayjs from 'dayjs'

const users = ref<Record<string, unknown>[]>([])
const loading = ref(false)
const syncing = ref(false)
const total = ref(0)
const currentPage = ref(1)
const search = ref('')
const roleFilter = ref('')
const statusFilter = ref('')

const permModalVisible = ref(false)
const saving = ref(false)
const selectedUser = ref<Record<string, unknown> | null>(null)
const permForm = reactive({
  max_concurrent_sessions: 3,
  max_session_duration_hours: 2,
  daily_session_quota: 10,
  can_start_terminal: true,
  can_view_monitoring: true,
  can_export_data: false,
})

const columns = [
  { title: '用户名', dataIndex: 'username', key: 'username' },
  { title: '邮箱', dataIndex: 'email', key: 'email' },
  { title: '角色', key: 'role' },
  { title: '状态', key: 'status' },
  { title: '最后登录', key: 'last_login_at' },
  { title: '总会话数', dataIndex: 'total_sessions', key: 'total_sessions' },
  { title: '操作', key: 'actions' },
]

async function loadUsers() {
  loading.value = true
  try {
    const res = await getAdminUsers({
      search: search.value || undefined,
      role: roleFilter.value || undefined,
      status: statusFilter.value || undefined,
      limit: 20,
      offset: (currentPage.value - 1) * 20,
    })
    const data = (res.data as { data: { users: Record<string, unknown>[]; total: number } }).data
    users.value = data.users
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function handleSync() {
  syncing.value = true
  try {
    const res = await syncUsers()
    const data = (res.data as { data: { synced_users: number; new_users: number } }).data
    message.success(`同步完成：共 ${data.synced_users} 个用户，新增 ${data.new_users} 个`)
    await loadUsers()
  } finally {
    syncing.value = false
  }
}

async function openPermissions(user: Record<string, unknown>) {
  selectedUser.value = user
  const res = await getAdminUser(user.id as number)
  const data = (res.data as { data: { permissions: typeof permForm } }).data
  if (data.permissions) {
    Object.assign(permForm, data.permissions)
  }
  permModalVisible.value = true
}

async function savePermissions() {
  if (!selectedUser.value) return
  saving.value = true
  try {
    await updateUserPermissions(selectedUser.value.id as number, { ...permForm })
    message.success('权限更新成功')
    permModalVisible.value = false
  } finally {
    saving.value = false
  }
}

function handlePageChange(page: number) {
  currentPage.value = page
  loadUsers()
}

onMounted(() => loadUsers())
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
