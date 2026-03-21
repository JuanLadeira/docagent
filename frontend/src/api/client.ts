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

export interface Agente {
  id: number
  nome: string
  descricao: string
  system_prompt: string | null
  skill_names: string[]
  ativo: boolean
  created_at: string
  updated_at: string
}

export interface AgenteCreate {
  nome: string
  descricao: string
  system_prompt: string | null
  skill_names: string[]
  ativo: boolean
}

export interface AgenteUpdate {
  nome?: string
  descricao?: string
  system_prompt?: string | null
  skill_names?: string[]
  ativo?: boolean
}

export interface WhatsappInstancia {
  id: number
  instance_name: string
  status: 'CRIADA' | 'CONECTANDO' | 'CONECTADA' | 'DESCONECTADA'
  tenant_id: number
  agente_id: number | null
  created_at: string
  updated_at: string
}

export interface InstanciaCreate {
  instance_name: string
  agente_id: number | null
}

export type AtendimentoStatus = 'ATIVO' | 'HUMANO' | 'ENCERRADO'
export type MensagemOrigem = 'CONTATO' | 'AGENTE' | 'OPERADOR'

export interface MensagemAtendimento {
  id: number
  origem: MensagemOrigem
  conteudo: string
  created_at: string
}

export interface Atendimento {
  id: number
  numero: string
  nome_contato: string | null
  instancia_id: number
  tenant_id: number
  status: AtendimentoStatus
  created_at: string
  updated_at: string
}

export interface AtendimentoDetalhe extends Atendimento {
  mensagens: MensagemAtendimento[]
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

  // Agentes
  listAgentes: () => apiClient.get<Agente[]>('/agentes/'),
  getAgente: (id: number) => apiClient.get<Agente>(`/agentes/${id}`),
  createAgente: (data: AgenteCreate) => apiClient.post<Agente>('/agentes/', data),
  updateAgente: (id: number, data: AgenteUpdate) => apiClient.put<Agente>(`/agentes/${id}`, data),
  deleteAgente: (id: number) => apiClient.delete(`/agentes/${id}`),

  // Atendimento
  criarAtendimento: (data: { instancia_id: number; numero: string; mensagem_inicial?: string }) =>
    apiClient.post<Atendimento>('/atendimentos', data),
  listAtendimentos: (status?: AtendimentoStatus) =>
    apiClient.get<Atendimento[]>('/atendimentos', { params: status ? { status } : undefined }),
  getAtendimento: (id: number) => apiClient.get<AtendimentoDetalhe>(`/atendimentos/${id}`),
  assumirAtendimento: (id: number) => apiClient.post<Atendimento>(`/atendimentos/${id}/assumir`),
  devolverAtendimento: (id: number) => apiClient.post<Atendimento>(`/atendimentos/${id}/devolver`),
  encerrarAtendimento: (id: number) => apiClient.post<Atendimento>(`/atendimentos/${id}/encerrar`),
  enviarMensagemOperador: (id: number, conteudo: string) =>
    apiClient.post<MensagemAtendimento>(`/atendimentos/${id}/mensagens`, { conteudo }),

  // WhatsApp
  listInstancias: () => apiClient.get<WhatsappInstancia[]>('/whatsapp/instancias'),
  createInstancia: (data: InstanciaCreate) =>
    apiClient.post<WhatsappInstancia>('/whatsapp/instancias', data),
  deleteInstancia: (id: number) => apiClient.delete(`/whatsapp/instancias/${id}`),
  getQrcode: (id: number) => apiClient.get<{ base64?: string; status?: string }>(`/whatsapp/instancias/${id}/qrcode`),
  sincronizarStatus: (id: number) =>
    apiClient.get<WhatsappInstancia>(`/whatsapp/instancias/${id}/status`),
}

/**
 * Subscreve eventos SSE de uma instância WhatsApp (QR code, status de conexão).
 * Usa fetch + ReadableStream (igual ao streamChat) pois EventSource não suporta Authorization header.
 * Retorna função de cleanup para cancelar a subscrição.
 */
export function subscribeInstanciaEventos(
  id: number,
  onEvent: (event: { type: string; [key: string]: unknown }) => void,
): () => void {
  let cancelled = false
  const token = sessionStorage.getItem('token') ?? ''
  const decoder = new TextDecoder()

  ;(async () => {
    try {
      const res = await fetch(`/api/whatsapp/instancias/${id}/eventos`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok || !res.body) return
      const reader = res.body.getReader()
      let buffer = ''
      while (!cancelled) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data:')) continue
          try {
            const event = JSON.parse(line.slice(5).trim())
            if (!cancelled) onEvent(event)
          } catch {
            // linha malformada
          }
        }
      }
      reader.cancel()
    } catch {
      // conexão encerrada
    }
  })()

  return () => {
    cancelled = true
  }
}

/**
 * Subscreve eventos SSE de um atendimento (novas mensagens em tempo real).
 */
export function subscribeAtendimentoEventos(
  id: number,
  onEvent: (event: { type: string; [key: string]: unknown }) => void,
): () => void {
  let cancelled = false
  const token = sessionStorage.getItem('token') ?? ''
  const decoder = new TextDecoder()

  ;(async () => {
    try {
      const res = await fetch(`/api/atendimentos/${id}/eventos`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok || !res.body) return
      const reader = res.body.getReader()
      let buffer = ''
      while (!cancelled) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data:')) continue
          try {
            const event = JSON.parse(line.slice(5).trim())
            if (!cancelled) onEvent(event)
          } catch {
            // linha malformada
          }
        }
      }
      reader.cancel()
    } catch {
      // conexão encerrada
    }
  })()

  return () => {
    cancelled = true
  }
}

export default apiClient
