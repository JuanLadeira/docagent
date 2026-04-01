import axios from 'axios'

const adminClient = axios.create({
  baseURL: '/api/admin',
  headers: { 'Content-Type': 'application/json' },
})

adminClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

adminClient.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('admin_token')
      localStorage.removeItem('admin_username')
      window.location.href = '/sys-mgmt/login'
    }
    return Promise.reject(error)
  },
)

// ── Types ────────────────────────────────────────────────────────────────────

export interface Tenant {
  id: number
  nome: string
  descricao: string | null
  llm_provider: string | null
  llm_model: string | null
  llm_api_key_set: boolean
  created_at: string
  updated_at: string
}

export type LlmMode = 'local' | 'api'

export interface SystemConfig {
  llm_mode: LlmMode
  [key: string]: string | undefined
}

export interface AdminUser {
  id: number
  username: string
  email: string
  nome: string
  ativo: boolean
  created_at: string
  updated_at: string
}

// ── Endpoints ────────────────────────────────────────────────────────────────

export const adminApi = {
  // Tenants
  getTenants: () => adminClient.get<Tenant[]>('/tenants'),
  createTenant: (data: { nome: string; descricao?: string }) =>
    adminClient.post<Tenant>('/tenants', data),
  updateTenant: (id: number, data: { nome?: string; descricao?: string; llm_provider?: string | null; llm_model?: string | null; llm_api_key?: string | null }) =>
    adminClient.put<Tenant>(`/tenants/${id}`, data),
  deleteTenant: (id: number) => adminClient.delete(`/tenants/${id}`),

  // Usuarios do tenant
  getTenantUsuarios: (tenantId: number) =>
    adminClient.get(`/tenants/${tenantId}/usuarios`),
  createTenantUsuario: (
    tenantId: number,
    data: { username: string; email: string; nome: string; password: string; role?: string },
  ) => adminClient.post(`/tenants/${tenantId}/usuarios`, data),
  updateUsuario: (id: number, data: Record<string, unknown>) =>
    adminClient.put(`/usuarios/${id}`, data),
  deleteUsuario: (id: number) => adminClient.delete(`/usuarios/${id}`),

  // Admins
  createAdmin: (data: { username: string; email: string; nome: string; password: string }) =>
    adminClient.post<AdminUser>('/admins', data),

  // System Config
  getSystemConfig: () => adminClient.get<SystemConfig>('/system-config'),
  updateSystemConfig: (data: Partial<SystemConfig>) => adminClient.put<SystemConfig>('/system-config', data),
}

export default adminClient
