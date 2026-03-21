import { defineStore } from 'pinia'
import { ref } from 'vue'
import { docagentApi } from '@/api/docagent'

export interface Message {
  role: 'user' | 'assistant'
  content: string
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

  // Persiste o sessionId
  sessionStorage.setItem('chat_session_id', sessionId.value)

  async function sendMessage(question: string) {
    messages.value.push({ role: 'user', content: question })
    isLoading.value = true
    currentStep.value = null

    try {
      const stream = docagentApi.streamChat(question, sessionId.value, selectedAgentId.value)
      for await (const event of stream) {
        if (event.type === 'step') {
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
  }

  return {
    sessionId,
    messages,
    isLoading,
    currentStep,
    selectedAgentId,
    lastUploadedFile,
    uploadFeedback,
    sendMessage,
    uploadDocument,
    resetSession,
  }
})
