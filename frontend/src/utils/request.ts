import axios from 'axios'
import { message } from 'ant-design-vue'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  withCredentials: true,
})

request.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail

    if (status === 401) {
      window.location.href = '/login'
      return Promise.reject(error)
    }

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
