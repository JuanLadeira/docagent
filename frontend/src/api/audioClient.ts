import apiClient from '@/api/client'

export interface AudioConfig {
  id: number
  tenant_id: number
  agente_id: number | null
  stt_habilitado: boolean
  stt_provider: 'faster_whisper' | 'openai'
  stt_modelo: string
  tts_habilitado: boolean
  tts_provider: 'piper' | 'openai' | 'elevenlabs'
  piper_voz: string
  openai_tts_voz: string
  elevenlabs_voice_id: string | null
  elevenlabs_api_key: string | null
  modo_resposta: 'audio_apenas' | 'texto_apenas' | 'audio_e_texto'
}

export type AudioConfigUpdate = Omit<AudioConfig, 'id' | 'tenant_id' | 'agente_id'>

export const audioApi = {
  async getDefault(): Promise<AudioConfig> {
    const r = await apiClient.get('/audio-config/default')
    return r.data
  },

  async saveDefault(data: AudioConfigUpdate): Promise<AudioConfig> {
    const r = await apiClient.put('/audio-config/default', data)
    return r.data
  },

  async getAgente(agenteId: number): Promise<AudioConfig> {
    const r = await apiClient.get(`/agentes/${agenteId}/audio-config`)
    return r.data
  },

  async saveAgente(agenteId: number, data: AudioConfigUpdate): Promise<AudioConfig> {
    const r = await apiClient.put(`/agentes/${agenteId}/audio-config`, data)
    return r.data
  },

  async deleteAgente(agenteId: number): Promise<void> {
    await apiClient.delete(`/agentes/${agenteId}/audio-config`)
  },
}
