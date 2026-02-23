<template>
  <div>
    <h2>个人设置</h2>

    <a-row :gutter="24">
      <a-col :span="12">
        <a-card title="基本信息" style="margin-bottom: 24px">
          <a-descriptions :column="1" bordered>
            <a-descriptions-item label="用户名">{{ user?.username }}</a-descriptions-item>
            <a-descriptions-item label="邮箱">{{ user?.email }}</a-descriptions-item>
            <a-descriptions-item label="姓名">{{ user?.full_name || '-' }}</a-descriptions-item>
            <a-descriptions-item label="角色">
              <a-tag :color="user?.role === 'admin' ? 'red' : 'blue'">
                {{ user?.role === 'admin' ? '管理员' : '普通用户' }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="所属组">
              <a-space wrap>
                <a-tag v-for="g in user?.groups" :key="g">{{ g }}</a-tag>
                <span v-if="!user?.groups?.length">-</span>
              </a-space>
            </a-descriptions-item>
          </a-descriptions>
        </a-card>

        <a-card title="我的配额">
          <a-descriptions :column="1" bordered>
            <a-descriptions-item label="最大并发会话数">
              {{ user?.permissions?.max_concurrent_sessions ?? 3 }}
            </a-descriptions-item>
            <a-descriptions-item label="单次会话最长时长">
              {{ user?.permissions?.max_session_duration_hours ?? 2 }} 小时
            </a-descriptions-item>
            <a-descriptions-item label="每日会话配额">
              {{ user?.permissions?.daily_session_quota ?? 10 }}
            </a-descriptions-item>
          </a-descriptions>
        </a-card>
      </a-col>

      <a-col :span="12">
        <a-card title="偏好设置">
          <a-form :model="prefForm" layout="vertical" @finish="savePref">
            <a-form-item label="界面语言">
              <a-select v-model:value="prefForm.language" style="width: 100%">
                <a-select-option value="zh-CN">中文（简体）</a-select-option>
                <a-select-option value="en-US">English</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item label="主题">
              <a-radio-group v-model:value="prefForm.theme">
                <a-radio-button value="light">浅色</a-radio-button>
                <a-radio-button value="dark">深色</a-radio-button>
              </a-radio-group>
            </a-form-item>
            <a-form-item label="时区">
              <a-select v-model:value="prefForm.timezone" style="width: 100%" show-search>
                <a-select-option v-for="tz in timezones" :key="tz" :value="tz">{{ tz }}</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item>
              <a-button type="primary" html-type="submit" :loading="saving">保存设置</a-button>
            </a-form-item>
          </a-form>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { getMyPreferences, updateMyPreferences } from '@/api/users'

const authStore = useAuthStore()
const { user } = storeToRefs(authStore)
const saving = ref(false)

const prefForm = reactive({
  language: 'zh-CN',
  theme: 'light',
  timezone: 'Asia/Shanghai',
})

const timezones = [
  'Asia/Shanghai', 'Asia/Tokyo', 'Asia/Seoul', 'Asia/Singapore',
  'America/New_York', 'America/Los_Angeles', 'America/Chicago',
  'Europe/London', 'Europe/Paris', 'Europe/Berlin',
  'UTC',
]

async function savePref() {
  saving.value = true
  try {
    await updateMyPreferences({ ...prefForm })
    message.success('设置已保存')
    await authStore.fetchCurrentUser()
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const res = await getMyPreferences()
    const data = (res.data as { data: typeof prefForm }).data
    Object.assign(prefForm, data)
  } catch {
    // use defaults
  }
})
</script>
