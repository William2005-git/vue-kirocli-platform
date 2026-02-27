import axios from 'axios'
import type { InternalAxiosRequestConfig } from 'axios'
import { message } from 'ant-design-vue'

// 扩展 AxiosRequestConfig 支持 _retry 标记
declare module 'axios' {
  interface InternalAxiosRequestConfig {
    _retry?: boolean
  }
}

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  withCredentials: true,
})

// 请求拦截器：携带设备指纹
request.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const fp = sessionStorage.getItem('device_fingerprint')
  if (fp && config.headers) {
    config.headers['X-Device-Fingerprint'] = fp
  }
  return config
})

let isRefreshing = false
let refreshQueue: Array<() => void> = []

request.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error.response?.status
    const config = error.config as InternalAxiosRequestConfig

    // 401 且非刷新请求本身 → 尝试刷新 Token
    if (status === 401 && !config._retry && !config.url?.includes('/auth/refresh')) {
      if (isRefreshing) {
        // 等待刷新完成后重试
        return new Promise((resolve) => {
          refreshQueue.push(() => resolve(request(config)))
        })
      }

      config._retry = true
      isRefreshing = true

      try {
        await request.post('/auth/refresh')
        refreshQueue.forEach(cb => cb())
        refreshQueue = []
        return request(config)
      } catch {
        refreshQueue = []
        window.location.href = '/login'
        return Promise.reject(error)
      } finally {
        isRefreshing = false
      }
    }

    const detail = error.response?.data?.detail
    const msg =
      (typeof detail === 'object' ? detail?.message : detail) ||
      error.message ||
      '请求失败'

    if (status !== 401) {
      message.error(msg)
    }

    return Promise.reject(error)
  }
)

export default request
