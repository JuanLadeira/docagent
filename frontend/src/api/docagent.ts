import axios from 'axios'

// ── Types ────────────────────────────────────────────────────────────────────

export interface Skill {
  name: string
  label: string
  icon: string
  description: string
}

export interface Agent {
  id: string
  name: string
  description: string
  skills: Skill[]
}

export interface UploadResponse {
  filename: string
  chunks: number
  collection_id: string
}

export type SseEvent =
  | { type: 'step'; content: string }
  | { type: 'answer'; content: string }
  | { type: 'meta'; conversa_id: number }
  | { type: 'done' }

// ── Endpoints ────────────────────────────────────────────────────────────────

export const docagentApi = {
  getAgents: () => axios.get<Agent[]>('/agents'),

  uploadDocument: (file: File, sessionId: string) => {
    const form = new FormData()
    form.append('file', file)
    form.append('session_id', sessionId)
    const token = sessionStorage.getItem('token') ?? ''
    return axios.post<UploadResponse>('/documents/upload', form, {
      headers: {
        'Content-Type': 'multipart/form-data',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
  },

  deleteSession: (sessionId: string) => {
    const token = sessionStorage.getItem('token') ?? ''
    return axios.delete(`/session/${sessionId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
  },

  /**
   * Transcreve um Blob de áudio gravado no browser via STT do backend.
   * Retorna o texto transcrito.
   */
  async transcribeAudio(audioBlob: Blob, agentId?: string | null): Promise<string> {
    const token = sessionStorage.getItem('token') ?? ''
    const form = new FormData()
    form.append('audio', audioBlob, 'recording.ogg')
    if (agentId && !isNaN(Number(agentId))) {
      form.append('agent_id', agentId)
    }
    const res = await fetch('/stt', {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    })
    if (!res.ok) throw new Error(`STT error: ${res.status}`)
    const data = await res.json()
    return data.transcription ?? ''
  },

  /**
   * Sintetiza texto em áudio OGG e retorna um blob URL reproduzível.
   * Chama TTS do backend com a AudioConfig do tenant/agente.
   */
  async synthesizeText(text: string, agentId?: string | null): Promise<string> {
    const token = sessionStorage.getItem('token') ?? ''
    const body: Record<string, unknown> = { text }
    if (agentId && !isNaN(Number(agentId))) body.agent_id = Number(agentId)
    const res = await fetch('/tts', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error(`TTS error: ${res.status}`)
    const blob = await res.blob()
    return URL.createObjectURL(blob)
  },

  /**
   * Inicia streaming SSE via fetch (Axios nao suporta ReadableStream em POST).
   * Retorna um AsyncGenerator que emite SseEvent conforme chegam do servidor.
   * conversa_id opcional: retoma conversa existente; se null, cria nova.
   */
  async *streamChat(
    question: string,
    sessionId: string,
    agentId: string,
    conversaId?: number | null,
  ): AsyncGenerator<SseEvent> {
    const token = sessionStorage.getItem('token') ?? ''
    const body: Record<string, unknown> = { question, session_id: sessionId, agent_id: agentId }
    if (conversaId != null) body.conversa_id = conversaId
    const res = await fetch('/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
    })

    if (!res.ok) throw new Error(`Chat error: ${res.status}`)

    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (!line.startsWith('data:')) continue
        try {
          const event = JSON.parse(line.slice(5).trim()) as SseEvent
          yield event
          if (event.type === 'done') return
        } catch {
          // linha malformada, ignora
        }
      }
    }
  },
}
