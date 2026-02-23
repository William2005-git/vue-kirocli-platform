<template>
  <a-layout-sider v-model:collapsed="collapsed" collapsible :width="220">
    <div class="logo">
      <span v-if="!collapsed">KiroCLI</span>
      <span v-else>K</span>
    </div>
    <a-menu
      v-model:selectedKeys="selectedKeys"
      theme="dark"
      mode="inline"
      @click="handleMenuClick"
    >
      <a-menu-item key="dashboard">
        <template #icon><dashboard-outlined /></template>
        <span>控制台</span>
      </a-menu-item>
      <a-menu-item key="sessions">
        <template #icon><code-outlined /></template>
        <span>终端管理</span>
      </a-menu-item>
      <a-menu-item v-if="isAdmin" key="monitoring">
        <template #icon><bar-chart-outlined /></template>
        <span>监控看板</span>
      </a-menu-item>
      <a-menu-item v-if="isAdmin" key="users">
        <template #icon><team-outlined /></template>
        <span>用户管理</span>
      </a-menu-item>
      <a-menu-item key="settings">
        <template #icon><setting-outlined /></template>
        <span>个人设置</span>
      </a-menu-item>
    </a-menu>
  </a-layout-sider>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  DashboardOutlined,
  CodeOutlined,
  BarChartOutlined,
  TeamOutlined,
  SettingOutlined,
} from '@ant-design/icons-vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const isAdmin = authStore.isAdmin

const collapsed = ref(false)
const selectedKeys = ref<string[]>([route.name as string || 'dashboard'])

watch(
  () => route.name,
  (name) => {
    if (name) selectedKeys.value = [name as string]
  }
)

function handleMenuClick({ key }: { key: string }) {
  router.push({ name: key.charAt(0).toUpperCase() + key.slice(1) })
}
</script>

<style scoped>
.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 18px;
  font-weight: bold;
  background: rgba(255, 255, 255, 0.1);
}
</style>
