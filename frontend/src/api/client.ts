import axios from 'axios'
import { useApiStatusStore } from '@/stores/apiStatus'

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
    if (error.response?.status === 502 || error.response?.status === 503 || !error.response) {
      try {
        useApiStatusStore().reportDown()
      } catch {
        // store not ready yet (before pinia init)
      }
    }
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
export type Prioridade = 'NORMAL' | 'ALTA' | 'URGENTE'
export type Canal = 'WHATSAPP' | 'TELEGRAM'

export interface MensagemAtendimento {
  id: number
  origem: MensagemOrigem
  conteudo: string
  tipo: 'text' | 'audio'
  media_ref: string | null
  created_at: string
}

export interface Atendimento {
  id: number
  numero: string
  nome_contato: string | null
  canal: Canal
  instancia_id: number | null
  telegram_instancia_id: number | null
  tenant_id: number
  status: AtendimentoStatus
  prioridade: Prioridade
  assumido_por_id: number | null
  assumido_por_nome: string | null
  contato_id: number | null
  created_at: string
  updated_at: string
}

export interface TelegramInstancia {
  id: number
  bot_username: string | null
  webhook_configured: boolean
  status: 'ATIVA' | 'INATIVA'
  cria_atendimentos: boolean
  tenant_id: number
  agente_id: number | null
  created_at: string
  updated_at: string
}

export interface TelegramInstanciaCreate {
  bot_token: string
  agente_id: number | null
  cria_atendimentos: boolean
}

export interface AtendimentoDetalhe extends Atendimento {
  mensagens: MensagemAtendimento[]
}

export interface Contato {
  id: number
  numero: string
  nome: string
  email: string | null
  notas: string | null
  instancia_id: number
  tenant_id: number
  created_at: string
  updated_at: string
}

export interface ContatoDetalhe extends Contato {
  atendimentos: Atendimento[]
}

export interface ContatoCreate {
  numero: string
  nome: string
  email?: string | null
  notas?: string | null
  instancia_id: number
}

export interface ContatoUpdate {
  nome?: string
  email?: string | null
  notas?: string | null
}

// ── Endpoints ────────────────────────────────────────────────────────────────

export interface McpTool {
  id: number
  server_id: number
  tool_name: string
  description: string
}

export interface McpServer {
  id: number
  nome: string
  descricao: string
  command: string
  args: string[]
  env: Record<string, string>
  ativo: boolean
  tools: McpTool[]
}

export interface Documento {
  id: number
  agente_id: number
  filename: string
  chunks: number
  collection_id?: string
  created_at: string
  updated_at: string
}

export interface Conversa {
  id: number
  agente_id: number
  agente_nome: string
  titulo: string | null
  created_at: string
  updated_at: string
  total_mensagens: number
}

export interface MensagemConversa {
  id: number
  role: 'user' | 'assistant' | 'tool' | 'system'
  conteudo: string
  tool_name: string | null
  created_at: string
}

export interface ConversaDetalhada extends Conversa {
  mensagens: MensagemConversa[]
}

export interface ConversaListResponse {
  items: Conversa[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

export interface McpServerCreate {
  nome: string
  descricao: string
  command: string
  args: string[]
  env: Record<string, string>
  ativo: boolean
}

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
  listAtendimentos: (status?: AtendimentoStatus, canal?: Canal) =>
    apiClient.get<Atendimento[]>('/atendimentos', {
      params: { ...(status ? { status } : {}), ...(canal ? { canal } : {}) },
    }),
  getAtendimento: (id: number) => apiClient.get<AtendimentoDetalhe>(`/atendimentos/${id}`),
  assumirAtendimento: (id: number) => apiClient.post<Atendimento>(`/atendimentos/${id}/assumir`),
  devolverAtendimento: (id: number) => apiClient.post<Atendimento>(`/atendimentos/${id}/devolver`),
  encerrarAtendimento: (id: number) => apiClient.post<Atendimento>(`/atendimentos/${id}/encerrar`),
  enviarMensagemOperador: (id: number, conteudo: string) =>
    apiClient.post<MensagemAtendimento>(`/atendimentos/${id}/mensagens`, { conteudo }),

  // Contatos
  criarContato: (data: ContatoCreate) => apiClient.post<Contato>('/atendimentos/contatos', data),
  listContatos: () => apiClient.get<Contato[]>('/atendimentos/contatos'),
  getContato: (id: number) => apiClient.get<ContatoDetalhe>(`/atendimentos/contatos/${id}`),
  atualizarContato: (id: number, data: ContatoUpdate) =>
    apiClient.patch<Contato>(`/atendimentos/contatos/${id}`, data),

  // Documentos por agente
  listDocumentos: (agenteId: number) =>
    apiClient.get<Documento[]>(`/agentes/${agenteId}/documentos`),
  uploadDocumento: (agenteId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return apiClient.post<Documento>(`/agentes/${agenteId}/documentos`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  removerDocumento: (agenteId: number, docId: number) =>
    apiClient.delete(`/agentes/${agenteId}/documentos/${docId}`),

  // MCP Servidores
  listMcpServidores: () => apiClient.get<McpServer[]>('/mcp-servidores'),
  createMcpServidor: (data: McpServerCreate) => apiClient.post<McpServer>('/mcp-servidores', data),
  updateMcpServidor: (id: number, data: Partial<McpServerCreate>) =>
    apiClient.put<McpServer>(`/mcp-servidores/${id}`, data),
  deleteMcpServidor: (id: number) => apiClient.delete(`/mcp-servidores/${id}`),
  descobrirTools: (id: number) => apiClient.post<McpTool[]>(`/mcp-servidores/${id}/descobrir-tools`),
  listMcpTools: (id: number) => apiClient.get<McpTool[]>(`/mcp-servidores/${id}/tools`),

  // WhatsApp
  listInstancias: () => apiClient.get<WhatsappInstancia[]>('/whatsapp/instancias'),
  createInstancia: (data: InstanciaCreate) =>
    apiClient.post<WhatsappInstancia>('/whatsapp/instancias', data),
  updateInstancia: (id: number, data: { agente_id: number | null }) =>
    apiClient.patch<WhatsappInstancia>(`/whatsapp/instancias/${id}`, data),
  deleteInstancia: (id: number) => apiClient.delete(`/whatsapp/instancias/${id}`),
  getQrcode: (id: number) => apiClient.get<{ base64?: string; status?: string }>(`/whatsapp/instancias/${id}/qrcode`),
  sincronizarStatus: (id: number) =>
    apiClient.get<WhatsappInstancia>(`/whatsapp/instancias/${id}/status`),

  // LLM Config (tenant owner)
  getLlmConfig: () =>
    apiClient.get<{ llm_provider: string | null; llm_model: string | null; llm_api_key_set: boolean }>('/tenants/me/llm-config'),
  updateLlmConfig: (data: { llm_provider?: string | null; llm_model?: string | null; llm_api_key?: string | null }) =>
    apiClient.put('/tenants/me/llm-config', data),

  // Conversas (Fase 19)
  listConversas: (params?: { agente_id?: number; arquivada?: boolean; page?: number; page_size?: number }) =>
    apiClient.get<ConversaListResponse>('/chat/conversas', { params }),
  getConversa: (id: number) =>
    apiClient.get<ConversaDetalhada>(`/chat/conversas/${id}`),
  arquivarConversa: (id: number) =>
    apiClient.delete(`/chat/conversas/${id}`),
  restaurarConversa: (id: number) =>
    apiClient.post(`/chat/conversas/${id}/restaurar`),

  // Telegram
  listTelegramInstancias: () => apiClient.get<TelegramInstancia[]>('/telegram/instancias'),
  createTelegramInstancia: (data: TelegramInstanciaCreate) =>
    apiClient.post<TelegramInstancia>('/telegram/instancias', data),
  updateTelegramInstancia: (id: number, data: { agente_id: number | null }) =>
    apiClient.patch<TelegramInstancia>(`/telegram/instancias/${id}`, data),
  deleteTelegramInstancia: (id: number) => apiClient.delete(`/telegram/instancias/${id}`),
  configurarTelegramWebhook: (id: number) =>
    apiClient.post<TelegramInstancia>(`/telegram/instancias/${id}/webhook/configurar`),
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

export type SseStatus = 'connecting' | 'connected' | 'disconnected'

/**
 * Subscreve eventos SSE da lista de atendimentos do tenant (NOVO_ATENDIMENTO, ATENDIMENTO_ATUALIZADO).
 * Reconecta automaticamente com backoff exponencial se a conexão cair.
 */
export function subscribeAtendimentoLista(
  onEvent: (event: { type: string; atendimento?: Atendimento; [key: string]: unknown }) => void,
  onStatus?: (status: SseStatus) => void,
): () => void {
  let cancelled = false
  const token = sessionStorage.getItem('token') ?? ''
  const decoder = new TextDecoder()
  const RETRY_DELAYS = [2000, 4000, 8000, 16000, 30000]
  let retryCount = 0

  async function connect() {
    while (!cancelled) {
      onStatus?.('connecting')
      try {
        const res = await fetch('/api/atendimentos/eventos', {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)
        retryCount = 0
        onStatus?.('connected')
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
        // conexão perdida
      }
      if (!cancelled) {
        onStatus?.('disconnected')
        const delay = RETRY_DELAYS[Math.min(retryCount, RETRY_DELAYS.length - 1)]
        retryCount++
        await new Promise((r) => setTimeout(r, delay))
      }
    }
  }

  connect()
  return () => { cancelled = true }
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
