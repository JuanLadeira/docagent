import apiClient from '@/api/client'

// ── Types ────────────────────────────────────────────────────────────────────

export type PipelineStatus =
  | 'PENDENTE'
  | 'ANALISANDO_CV'
  | 'BUSCANDO_VAGAS'
  | 'PERSONALIZANDO'
  | 'REGISTRANDO'
  | 'CONCLUIDO'
  | 'ERRO'

export type CandidaturaStatus = 'AGUARDANDO_ENVIO' | 'ENVIADA' | 'REJEITADA'
export type FonteVaga = 'DUCKDUCKGO' | 'GUPY' | 'LINKEDIN' | 'INDEED'

export const FONTES_DISPONIVEIS: FonteVaga[] = ['GUPY', 'DUCKDUCKGO', 'LINKEDIN', 'INDEED']

export interface PipelineConfig {
  max_vagas_por_fonte: number
  max_personalizar: number
  fontes: FonteVaga[]
  candidatura_simplificada: boolean
  apenas_simplificadas: boolean
}

export function defaultConfig(): PipelineConfig {
  return {
    max_vagas_por_fonte: 20,
    max_personalizar: 10,
    fontes: [...FONTES_DISPONIVEIS],
    candidatura_simplificada: false,
    apenas_simplificadas: false,
  }
}

export interface CandidatoPerfil {
  id: number
  nome: string
  cargo_desejado: string
  email: string
  skills: string[]
  cv_filename: string
  created_at: string
}

export interface PipelineRun {
  id: number
  tenant_id: number
  usuario_id: number
  candidato_id: number | null
  status: PipelineStatus
  etapa_atual: string | null
  erro: string | null
  vagas_encontradas: number
  candidaturas_criadas: number
  created_at: string
}

export interface Vaga {
  id: number
  tenant_id: number
  pipeline_run_id: number
  titulo: string
  empresa: string
  localizacao: string
  descricao: string
  requisitos: string
  url: string
  fonte: FonteVaga
  match_score: number
  candidatura_simplificada: boolean
  created_at: string
}

export interface Candidatura {
  id: number
  tenant_id: number
  pipeline_run_id: number
  vaga_id: number
  candidato_id: number
  resumo_personalizado: string
  carta_apresentacao: string
  status: CandidaturaStatus
  simplificada: boolean
  created_at: string
}

export interface PipelineRunDetalhe extends PipelineRun {
  vagas: Vaga[]
  candidaturas: Candidatura[]
}

export interface PipelineIniciadoResponse {
  pipeline_run_id: number
  status: PipelineStatus
  message: string
}

// ── API ──────────────────────────────────────────────────────────────────────

export const vagasApi = {
  iniciarPipeline: (cv: File, config?: Partial<PipelineConfig>) => {
    const form = new FormData()
    form.append('cv', cv)
    const cfg = { ...defaultConfig(), ...config }
    form.append('config_json', JSON.stringify(cfg))
    return apiClient.post<PipelineIniciadoResponse>('/vagas/pipeline', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  listarPipelines: () => apiClient.get<PipelineRun[]>('/vagas/pipelines'),

  getPipelineDetalhe: (runId: number) =>
    apiClient.get<PipelineRunDetalhe>(`/vagas/pipelines/${runId}`),

  listarVagas: (pipelineRunId: number, minScore = 0.0) =>
    apiClient.get<Vaga[]>('/vagas/vagas', {
      params: { pipeline_run_id: pipelineRunId, min_score: minScore },
    }),

  listarCandidaturas: (pipelineRunId: number, status?: CandidaturaStatus) =>
    apiClient.get<Candidatura[]>('/vagas/candidaturas', {
      params: { pipeline_run_id: pipelineRunId, ...(status ? { status } : {}) },
    }),

  getCandidatura: (id: number) => apiClient.get<Candidatura>(`/vagas/candidaturas/${id}`),

  atualizarStatusCandidatura: (id: number, status: CandidaturaStatus) =>
    apiClient.patch<Candidatura>(`/vagas/candidaturas/${id}`, { status }),

  downloadPdfCandidatura: (id: number) =>
    apiClient.get(`/vagas/candidaturas/${id}/pdf`, { responseType: 'blob' }),

  listarCandidatos: () => apiClient.get<CandidatoPerfil[]>('/vagas/candidatos'),

  reutilizarPipeline: (candidatoId: number, config?: Partial<PipelineConfig>) => {
    const form = new FormData()
    const cfg = { ...defaultConfig(), ...config }
    form.append('config_json', JSON.stringify(cfg))
    return apiClient.post<PipelineIniciadoResponse>(
      `/vagas/candidatos/${candidatoId}/pipeline`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
  },
}

// ── SSE ──────────────────────────────────────────────────────────────────────

export type PipelineEvent =
  | { type: 'PROGRESSO'; etapa: string; mensagem: string }
  | { type: 'CONCLUIDO'; vagas_encontradas: number; candidaturas_criadas: number }
  | { type: 'ERRO'; mensagem: string }
  | { type: 'ping' }

export function subscribePipelineEventos(
  runId: number,
  onEvent: (event: PipelineEvent) => void,
  onClose?: () => void,
): () => void {
  let cancelled = false
  const token = sessionStorage.getItem('token') ?? ''
  const decoder = new TextDecoder()

  ;(async () => {
    try {
      const res = await fetch(`/api/vagas/pipeline/${runId}/eventos`, {
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
            const event = JSON.parse(line.slice(5).trim()) as PipelineEvent
            if (!cancelled) onEvent(event)
          } catch {
            // linha malformada
          }
        }
      }
      reader.cancel()
    } catch {
      // conexão encerrada
    } finally {
      if (!cancelled) onClose?.()
    }
  })()

  return () => {
    cancelled = true
  }
}
