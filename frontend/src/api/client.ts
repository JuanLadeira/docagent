import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

apiClient.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) {
      sessionStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

// ── Types ────────────────────────────────────────────────────────────────────

export interface Usuario {
  id: number
  username: string
  email: string
  nome: string
  ativo: boolean
  role: 'OWNER' | 'MEMBER'
  tenant_id: number
  created_at: string
  updated_at: string
}

// ── Endpoints ────────────────────────────────────────────────────────────────

export const api = {
  login: (username: string, password: string) =>
    axios.post<{ access_token: string; token_type: string }>(
      '/auth/login',
      new URLSearchParams({ username, password }),
    ),

  getMe: () => apiClient.get<Usuario>('/usuarios/me'),

  forgotPassword: (email: string) =>
    axios.post('/auth/forgot-password', { email }),

  resetPassword: (token: string, new_password: string) =>
    axios.post('/auth/reset-password', { token, new_password }),

  changePassword: (current_password: string, new_password: string) =>
    apiClient.post('/auth/change-password', { current_password, new_password }),
}

export default apiClient
