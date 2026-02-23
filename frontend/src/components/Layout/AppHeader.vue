<template>
  <a-layout-header class="app-header">
    <div class="header-right">
      <a-dropdown>
        <a-space class="user-info">
          <user-outlined />
          <span>{{ user?.full_name || user?.username }}</span>
          <a-tag :color="user?.role === 'admin' ? 'red' : 'blue'" size="small">
            {{ user?.role === 'admin' ? '管理员' : '普通用户' }}
          </a-tag>
        </a-space>
        <template #overlay>
          <a-menu>
            <a-menu-item key="settings" @click="$router.push('/settings')">
              <setting-outlined /> 个人设置
            </a-menu-item>
            <a-menu-divider />
            <a-menu-item key="logout" @click="handleLogout">
              <logout-outlined /> 退出登录
            </a-menu-item>
          </a-menu>
        </template>
      </a-dropdown>
    </div>
  </a-layout-header>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { UserOutlined, SettingOutlined, LogoutOutlined } from '@ant-design/icons-vue'
import { storeToRefs } from 'pinia'

const authStore = useAuthStore()
const { user } = storeToRefs(authStore)

async function handleLogout() {
  await authStore.logout()
}
</script>

<style scoped>
.app-header {
  background: #fff;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}
.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}
.user-info {
  cursor: pointer;
}
</style>
