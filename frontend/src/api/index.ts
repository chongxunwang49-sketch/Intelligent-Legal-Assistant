import axios, { type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

export const TOKEN_KEY = 'zhifatong_token'
export const REFRESH_KEY = 'zhifatong_refresh'

const instance = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
})

instance.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

instance.interceptors.response.use(
  (resp) => resp.data,
  (err) => {
    const status = err?.response?.status
    const detail = err?.response?.data?.detail
    if (status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(REFRESH_KEY)
      if (!location.pathname.startsWith('/login')) location.href = '/login'
    } else if (status === 429) {
      ElMessage.warning(detail || '操作过于频繁或额度已用完')
    } else if (detail) {
      const msg = typeof detail === 'string' ? detail : (detail[0]?.msg || '请求失败')
      ElMessage.error(msg)
    } else {
      ElMessage.error('网络错误，请稍后重试')
    }
    return Promise.reject(err)
  }
)

export const http = {
  get: <T = any>(url: string, config?: AxiosRequestConfig) => instance.get(url, config) as Promise<T>,
  post: <T = any>(url: string, data?: any, config?: AxiosRequestConfig) => instance.post(url, data, config) as Promise<T>,
  put: <T = any>(url: string, data?: any) => instance.put(url, data) as Promise<T>,
  patch: <T = any>(url: string, data?: any) => instance.patch(url, data) as Promise<T>,
  delete: <T = any>(url: string) => instance.delete(url) as Promise<T>,
}

export default http
