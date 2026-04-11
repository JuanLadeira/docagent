import { defineStore } from 'pinia'
import { ref } from 'vue'
import { docagentApi } from '@/api/docagent'
import { api, type Conversa } from '@/api/client'

export interface Message {
  role: 'user' | 'assistant'
  content: string
  audioUrl?: string   // blob URL: gravação do usuário ou TTS do agente (revogado após uso)
}

export const useChatStore = defineStore('chat', () => {
  const sessionId = ref<string>(
    sessionStorage.getItem('chat_session_id') ?? crypto.randomUUID(),
  )
  const messages = ref<Message[]>([])
  const isLoading = ref(false)
  const currentStep = ref<string | null>(null)
  const selectedAgentId = ref<string>('doc-analyst')
  const lastUploadedFile = ref<string | null>(null)
  const uploadFeedback = ref<string | null>(null)

  // Fase 19 — histórico de conversas
  const conversaId = ref<number | null>(null)
  const conversas = ref<Conversa[]>([])
  const conversasPage = ref(1)
  const conversasHasMore = ref(false)
  const conversasLoading = ref(false)

  // Persiste o sessionId
  sessionStorage.setItem('chat_session_id', sessionId.value)

  async function sendMessage(question: string) {
    messages.value.push({ role: 'user', content: question })
    isLoading.value = true
    currentStep.value = null

    try {
      const stream = docagentApi.streamChat(
        question,
        sessionId.value,
        selectedAgentId.value,
        conversaId.value,
      )
      for await (const event of stream) {
        if (event.type === 'meta') {
          // Captura o conversa_id retornado pelo backend
          conversaId.value = event.conversa_id
        } else if (event.type === 'step') {
          currentStep.value = event.content
        } else if (event.type === 'answer') {
          currentStep.value = null
          messages.value.push({ role: 'assistant', content: event.content })
        } else if (event.type === 'done') {
          break
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Erro ao conectar ao agente'
      messages.value.push({ role: 'assistant', content: `⚠️ ${msg}` })
    } finally {
      isLoading.value = false
      currentStep.value = null
      // Atualiza a lista de conversas após cada mensagem
      await fetchConversas(true)
    }
  }

  /**
   * Transcreve o Blob de áudio, envia como mensagem e pede TTS para a resposta.
   * O user message recebe o audioUrl da gravação; o assistant message recebe o TTS.
   */
  async function sendAudioMessage(audioBlob: Blob) {
    isLoading.value = true
    currentStep.value = null

    // URL local para reproduzir a gravação do próprio usuário
    const recordingUrl = URL.createObjectURL(audioBlob)

    try {
      const transcription = await docagentApi.transcribeAudio(audioBlob, selectedAgentId.value)
      if (!transcription) {
        isLoading.value = false
        return
      }

      // Adiciona a mensagem do usuário com o blob de áudio
      messages.value.push({ role: 'user', content: transcription, audioUrl: recordingUrl })

      const stream = docagentApi.streamChat(
        transcription,
        sessionId.value,
        selectedAgentId.value,
        conversaId.value,
      )

      let assistantContent = ''
      for await (const event of stream) {
        if (event.type === 'meta') {
          conversaId.value = event.conversa_id
        } else if (event.type === 'step') {
          currentStep.value = event.content
        } else if (event.type === 'answer') {
          currentStep.value = null
          assistantContent = event.content
          messages.value.push({ role: 'assistant', content: assistantContent })
        } else if (event.type === 'done') {
          break
        }
      }

      // Gera TTS para a resposta do agente e atualiza o audioUrl da última mensagem
      if (assistantContent) {
        try {
          const ttsUrl = await docagentApi.synthesizeText(assistantContent, selectedAgentId.value)
          const last = messages.value[messages.value.length - 1]
          if (last?.role === 'assistant') last.audioUrl = ttsUrl
        } catch {
          // TTS opcional — silencioso se falhar (ex: TTS desabilitado)
        }
      }
    } catch (err) {
      URL.revokeObjectURL(recordingUrl)
      const msg = err instanceof Error ? err.message : 'Erro ao processar áudio'
      messages.value.push({ role: 'assistant', content: `⚠️ ${msg}` })
    } finally {
      isLoading.value = false
      currentStep.value = null
      await fetchConversas(true)
    }
  }

  async function uploadDocument(file: File) {
    try {
      const res = await docagentApi.uploadDocument(file, sessionId.value)
      lastUploadedFile.value = file.name
      uploadFeedback.value = `✅ ${res.data.chunks} chunks indexados`
    } catch {
      uploadFeedback.value = '⚠️ Erro no upload'
    }
  }

  async function resetSession() {
    try {
      await docagentApi.deleteSession(sessionId.value)
    } catch {
      // ignora erros ao deletar sessao
    }
    sessionId.value = crypto.randomUUID()
    sessionStorage.setItem('chat_session_id', sessionId.value)
    messages.value = []
    currentStep.value = null
    lastUploadedFile.value = null
    uploadFeedback.value = null
    conversaId.value = null
  }

  async function fetchConversas(reset = false) {
    if (conversasLoading.value) return
    conversasLoading.value = true
    try {
      const page = reset ? 1 : conversasPage.value
      const agId = selectedAgentId.value && !isNaN(Number(selectedAgentId.value))
        ? Number(selectedAgentId.value)
        : undefined
      const res = await api.listConversas({
        agente_id: agId,
        arquivada: false,
        page,
        page_size: 20,
      })
      if (reset) {
        conversas.value = res.data.items
        conversasPage.value = 1
      } else {
        conversas.value.push(...res.data.items)
      }
      conversasHasMore.value = res.data.has_more
      if (!reset) conversasPage.value = page + 1
    } catch {
      // silencioso
    } finally {
      conversasLoading.value = false
    }
  }

  async function carregarConversa(id: number) {
    try {
      const res = await api.getConversa(id)
      const det = res.data
      conversaId.value = det.id
      messages.value = det.mensagens
        .filter(m => m.role === 'user' || m.role === 'assistant')
        .map(m => ({ role: m.role as 'user' | 'assistant', content: m.conteudo }))
    } catch {
      // silencioso
    }
  }

  async function arquivarConversa(id: number) {
    try {
      await api.arquivarConversa(id)
      conversas.value = conversas.value.filter(c => c.id !== id)
      if (conversaId.value === id) {
        await resetSession()
      }
    } catch {
      // silencioso
    }
  }

  return {
    sessionId,
    messages,
    isLoading,
    currentStep,
    selectedAgentId,
    lastUploadedFile,
    uploadFeedback,
    conversaId,
    conversas,
    conversasHasMore,
    conversasLoading,
    sendMessage,
    sendAudioMessage,
    uploadDocument,
    resetSession,
    fetchConversas,
    carregarConversa,
    arquivarConversa,
  }
})
