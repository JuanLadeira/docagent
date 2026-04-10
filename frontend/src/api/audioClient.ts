import axios from 'axios'

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

const BASE = import.meta.env.VITE_API_URL ?? ''

function authHeader() {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export const audioApi = {
  async getDefault(): Promise<AudioConfig> {
    const r = await axios.get(`${BASE}/api/audio-config/default`, { headers: authHeader() })
    return r.data
  },

  async saveDefault(data: AudioConfigUpdate): Promise<AudioConfig> {
    const r = await axios.put(`${BASE}/api/audio-config/default`, data, { headers: authHeader() })
    return r.data
  },

  async getAgente(agenteId: number): Promise<AudioConfig> {
    const r = await axios.get(`${BASE}/api/agentes/${agenteId}/audio-config`, { headers: authHeader() })
    return r.data
  },

  async saveAgente(agenteId: number, data: AudioConfigUpdate): Promise<AudioConfig> {
    const r = await axios.put(`${BASE}/api/agentes/${agenteId}/audio-config`, data, { headers: authHeader() })
    return r.data
  },

  async deleteAgente(agenteId: number): Promise<void> {
    await axios.delete(`${BASE}/api/agentes/${agenteId}/audio-config`, { headers: authHeader() })
  },
}
