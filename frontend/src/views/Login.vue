<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">
        <code-outlined class="logo-icon" />
        <h1>KiroCLI Platform</h1>
        <p>基于 AWS IAM Identity Center 的终端管理平台</p>
      </div>
      <a-button
        type="primary"
        size="large"
        block
        :loading="loading"
        @click="handleLogin"
      >
        <template #icon><login-outlined /></template>
        使用 IAM Identity Center 登录
      </a-button>
      <div class="login-footer">
        <a-typography-text type="secondary">
          登录即表示您同意使用条款和隐私政策
        </a-typography-text>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { CodeOutlined, LoginOutlined } from '@ant-design/icons-vue'

const loading = ref(false)

function handleLogin() {
  loading.value = true
  window.location.href = '/api/v1/auth/saml/login'
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.login-card {
  background: white;
  border-radius: 16px;
  padding: 48px 40px;
  width: 420px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
}
.login-logo {
  text-align: center;
  margin-bottom: 40px;
}
.logo-icon {
  font-size: 48px;
  color: #1890ff;
  margin-bottom: 16px;
}
.login-logo h1 {
  font-size: 24px;
  font-weight: 700;
  margin: 8px 0;
  color: #1a1a2e;
}
.login-logo p {
  color: #666;
  font-size: 14px;
}
.login-footer {
  text-align: center;
  margin-top: 24px;
}
</style>
