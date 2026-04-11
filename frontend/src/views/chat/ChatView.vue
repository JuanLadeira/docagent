<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useAgentsStore } from '@/stores/agents'
import { api, type Documento } from '@/api/client'

const chat = useChatStore()
const agentsStore = useAgentsStore()

const input = ref('')
const messagesEl = ref<HTMLElement | null>(null)
const fileInputEl = ref<HTMLInputElement | null>(null)
const isUploading = ref(false)
const documentos = ref<Documento[]>([])
const loadingDocs = ref(false)
const docError = ref('')
const sidebarTab = ref<'conversas' | 'docs'>('conversas')
const conversasSidebarEl = ref<HTMLElement | null>(null)

// ── Gravação de áudio ─────────────────────────────────────────────────────────
const isRecording = ref(false)
const recordingSeconds = ref(0)
let mediaRecorder: MediaRecorder | null = null
let recordingInterval: ReturnType<typeof setInterval> | null = null

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const chunks: BlobPart[] = []
    // Prefere ogg/opus (melhor compatibilidade com faster-whisper); fallback para webm
    const mimeType = MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')
      ? 'audio/ogg;codecs=opus'
      : 'audio/webm'
    mediaRecorder = new MediaRecorder(stream, { mimeType })
    mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data) }
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop())
      const blob = new Blob(chunks, { type: mimeType })
      isRecording.value = false
      recordingSeconds.value = 0
      if (recordingInterval) { clearInterval(recordingInterval); recordingInterval = null }
      await chat.sendAudioMessage(blob)
    }
    mediaRecorder.start()
    isRecording.value = true
    recordingSeconds.value = 0
    recordingInterval = setInterval(() => recordingSeconds.value++, 1000)
  } catch {
    alert('Não foi possível acessar o microfone.')
  }
}

function stopRecording() {
  mediaRecorder?.stop()
}

function formatRecordingTime(s: number) {
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

onMounted(async () => {
  await agentsStore.fetchIfNeeded()
  // Auto-seleciona o primeiro agente se nenhum válido estiver selecionado
  if (isNaN(Number(chat.selectedAgentId)) && agentsStore.agents.length > 0) {
    chat.selectedAgentId = String(agentsStore.agents[0].id)
  }
  if (chat.selectedAgentId) loadDocumentos(chat.selectedAgentId)
  await chat.fetchConversas(true)
})

watch(() => chat.selectedAgentId, (id) => {
  if (id) loadDocumentos(id)
  chat.fetchConversas(true)
})

watch(
  () => [chat.messages.length, chat.currentStep],
  () => nextTick(scrollToBottom),
)

function scrollToBottom() {
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
}

async function handleSend() {
  const q = input.value.trim()
  if (!q || chat.isLoading) return
  input.value = ''
  await chat.sendMessage(q)
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function selectAgent(id: string) {
  chat.selectedAgentId = id
  loadDocumentos(id)
}

async function selectAgentFromDocs(id: string) {
  chat.selectedAgentId = id
  loadDocumentos(id)

  const numericId = Number(id)
  if (!numericId) return

  // Busca a conversa mais recente desse agente
  try {
    const res = await api.listConversas({ agente_id: numericId, arquivada: false, page: 1, page_size: 1 })
    if (res.data.items.length > 0) {
      await chat.carregarConversa(res.data.items[0].id)
    } else {
      await chat.resetSession()
    }
    await chat.fetchConversas(true)
  } catch {
    await chat.resetSession()
  }

  // Vai para a aba de conversas para mostrar o resultado
  sidebarTab.value = 'conversas'
}

async function loadDocumentos(agentId: string) {
  const numericId = Number(agentId)
  if (!numericId) return
  loadingDocs.value = true
  docError.value = ''
  try {
    const res = await api.listDocumentos(numericId)
    documentos.value = res.data
  } catch {
    documentos.value = []
  } finally {
    loadingDocs.value = false
  }
}

async function handleFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  const numericId = Number(chat.selectedAgentId)
  if (!numericId) return
  isUploading.value = true
  docError.value = ''
  try {
    const res = await api.uploadDocumento(numericId, file)
    documentos.value.push(res.data)
  } catch (err: unknown) {
    const status = (err as { response?: { status?: number } })?.response?.status
    docError.value = status === 409
      ? 'Este arquivo já foi indexado para este agente.'
      : 'Erro ao indexar documento.'
  } finally {
    isUploading.value = false
    if (fileInputEl.value) fileInputEl.value.value = ''
  }
}

async function removerDocumento(docId: number) {
  const numericId = Number(chat.selectedAgentId)
  if (!numericId) return
  try {
    await api.removerDocumento(numericId, docId)
    documentos.value = documentos.value.filter(d => d.id !== docId)
  } catch {
    docError.value = 'Erro ao remover documento.'
  }
}

function triggerUpload() {
  fileInputEl.value?.click()
}

// ── Conversas ─────────────────────────────────────────────────────────────────

function groupConversasByDate(conversas: typeof chat.conversas) {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1)
  const weekAgo = new Date(today); weekAgo.setDate(weekAgo.getDate() - 7)

  const groups: { label: string; items: typeof conversas }[] = [
    { label: 'Hoje', items: [] },
    { label: 'Ontem', items: [] },
    { label: 'Esta semana', items: [] },
    { label: 'Mais antigas', items: [] },
  ]

  for (const c of conversas) {
    const d = new Date(c.updated_at)
    const day = new Date(d.getFullYear(), d.getMonth(), d.getDate())
    if (day >= today) groups[0].items.push(c)
    else if (day >= yesterday) groups[1].items.push(c)
    else if (day >= weekAgo) groups[2].items.push(c)
    else groups[3].items.push(c)
  }

  return groups.filter(g => g.items.length > 0)
}

async function onSidebarScroll() {
  const el = conversasSidebarEl.value
  if (!el) return
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 40 && chat.conversasHasMore && !chat.conversasLoading) {
    await chat.fetchConversas()
  }
}
</script>

<template>
  <div class="flex h-full bg-slate-50 dark:bg-slate-900">
    <!-- ─── Sidebar ─────────────────────────────────────────────────────── -->
    <aside class="w-72 flex-shrink-0 flex flex-col border-r border-slate-700" style="background: #0f172a">
      <!-- Header with tabs -->
      <div class="p-4 border-b border-slate-700">
        <div class="flex gap-1 bg-slate-800 rounded-lg p-1">
          <button
            @click="sidebarTab = 'conversas'"
            class="flex-1 text-xs py-1.5 rounded-md transition-colors"
            :class="sidebarTab === 'conversas' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'"
          >
            Conversas
          </button>
          <button
            @click="sidebarTab = 'docs'"
            class="flex-1 text-xs py-1.5 rounded-md transition-colors"
            :class="sidebarTab === 'docs' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'"
          >
            Docs
          </button>
        </div>
      </div>

      <!-- ─── Tab: Conversas ─────────────────────────────────────────────── -->
      <template v-if="sidebarTab === 'conversas'">
        <!-- Agent selector (compact) -->
        <div class="px-4 pt-3 pb-2">
          <label class="block text-slate-400 text-xs uppercase tracking-wider mb-1">Agente</label>
          <div v-if="agentsStore.isFetching" class="text-slate-500 text-xs">Carregando...</div>
          <select
            v-else
            :value="chat.selectedAgentId"
            @change="selectAgent(($event.target as HTMLSelectElement).value)"
            class="w-full bg-slate-800 border border-slate-600 text-slate-300 text-xs rounded-lg px-2 py-1.5 outline-none focus:ring-1 focus:ring-indigo-400"
          >
            <option v-for="agent in agentsStore.agents" :key="agent.id" :value="String(agent.id)">
              {{ agent.nome }}
            </option>
          </select>
        </div>

        <!-- Conversation list with infinite scroll -->
        <div
          ref="conversasSidebarEl"
          class="flex-1 overflow-y-auto px-2 py-1"
          @scroll="onSidebarScroll"
        >
          <div v-if="chat.conversasLoading && chat.conversas.length === 0" class="text-slate-500 text-xs py-4 text-center">
            Carregando...
          </div>

          <div v-else-if="chat.conversas.length === 0" class="text-slate-500 text-xs py-4 text-center">
            Nenhuma conversa ainda.
          </div>

          <template v-else>
            <div v-for="group in groupConversasByDate(chat.conversas)" :key="group.label" class="mb-3">
              <div class="text-slate-500 text-xs px-2 py-1 uppercase tracking-wider">{{ group.label }}</div>
              <button
                v-for="c in group.items"
                :key="c.id"
                @click="chat.carregarConversa(c.id)"
                class="w-full text-left px-3 py-2 rounded-lg text-xs transition-colors group flex items-center justify-between gap-2"
                :class="
                  chat.conversaId === c.id
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-300 hover:bg-slate-700'
                "
              >
                <span class="truncate">
                  {{ c.titulo ?? 'Nova conversa' }}
                </span>
                <button
                  @click.stop="chat.arquivarConversa(c.id)"
                  title="Arquivar"
                  class="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-400 transition-all shrink-0 text-xs"
                >
                  ✕
                </button>
              </button>
            </div>

            <div v-if="chat.conversasLoading" class="text-slate-500 text-xs text-center py-2">
              Carregando mais...
            </div>
          </template>
        </div>

        <!-- Nova conversa -->
        <div class="p-4 border-t border-slate-700">
          <button
            @click="chat.resetSession()"
            :disabled="chat.isLoading"
            class="w-full text-left px-3 py-2 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-slate-700 transition-colors disabled:opacity-50"
          >
            + Nova conversa
          </button>
        </div>
      </template>

      <!-- ─── Tab: Documentos ───────────────────────────────────────────── -->
      <template v-else>
        <div class="flex-1 p-4 space-y-4 overflow-y-auto">
          <!-- Agent selector -->
          <div>
            <label class="block text-slate-400 text-xs uppercase tracking-wider mb-2">Agente</label>
            <div v-if="agentsStore.isFetching" class="text-slate-500 text-xs">Carregando...</div>
            <div v-else class="space-y-1">
              <button
                v-for="agent in agentsStore.agents"
                :key="agent.id"
                @click="selectAgentFromDocs(String(agent.id))"
                class="w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors"
                :class="
                  chat.selectedAgentId === String(agent.id)
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-300 hover:bg-slate-700'
                "
              >
                <div class="font-medium">{{ agent.nome }}</div>
                <div class="text-xs mt-0.5 opacity-70 flex flex-wrap gap-x-2">
                  <span v-for="skill in agent.skill_names" :key="skill">{{ skill }}</span>
                </div>
              </button>
            </div>
          </div>

          <!-- Base de Conhecimento -->
          <div>
            <div class="flex items-center justify-between mb-2">
              <label class="block text-slate-400 text-xs uppercase tracking-wider">
                Base de Conhecimento
              </label>
              <button
                v-if="chat.selectedAgentId"
                @click="triggerUpload"
                :disabled="isUploading"
                title="Adicionar PDF"
                class="text-slate-400 hover:text-white transition-colors disabled:opacity-40 text-sm"
              >
                +
              </button>
            </div>

            <input
              ref="fileInputEl"
              type="file"
              accept=".pdf"
              class="hidden"
              @change="handleFileChange"
            />

            <div v-if="!chat.selectedAgentId" class="text-slate-500 text-xs py-1">
              Selecione um agente.
            </div>

            <div v-else-if="loadingDocs" class="text-slate-500 text-xs py-1">
              Carregando...
            </div>

            <div v-else class="space-y-1">
              <div
                v-for="doc in documentos"
                :key="doc.id"
                class="flex items-center justify-between gap-2 px-2 py-1.5 rounded-lg bg-slate-800 group"
              >
                <div class="min-w-0 flex-1">
                  <div class="text-slate-300 text-xs font-medium truncate" :title="doc.filename">
                    {{ doc.filename }}
                  </div>
                  <div class="text-slate-500 text-xs">{{ doc.chunks }} chunks</div>
                </div>
                <button
                  @click="removerDocumento(doc.id)"
                  title="Remover documento"
                  class="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-red-400 transition-all text-xs shrink-0"
                >
                  ✕
                </button>
              </div>

              <div v-if="documentos.length === 0" class="text-slate-500 text-xs py-1">
                Nenhum documento indexado.
                <button @click="triggerUpload" class="text-indigo-400 hover:text-indigo-300 underline ml-1">
                  Adicionar PDF
                </button>
              </div>
            </div>

            <div v-if="isUploading" class="mt-2 flex items-center gap-2 text-xs text-slate-400">
              <span class="inline-block w-3 h-3 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></span>
              Indexando...
            </div>

            <div v-if="docError" class="mt-2 text-xs text-red-400 bg-red-900/30 px-2 py-1 rounded">
              {{ docError }}
            </div>
          </div>
        </div>
      </template>
    </aside>

    <!-- ─── Main chat area ─────────────────────────────────────────────── -->
    <div class="flex-1 flex flex-col min-w-0 bg-slate-50 dark:bg-slate-900">
      <!-- Messages -->
      <div ref="messagesEl" class="flex-1 overflow-y-auto p-6 space-y-4">
        <!-- Empty state -->
        <div
          v-if="chat.messages.length === 0 && !chat.isLoading"
          class="flex flex-col items-center justify-center h-full text-center"
        >
          <div class="text-6xl mb-4">📄</div>
          <h3 class="text-slate-700 dark:text-slate-200 font-semibold text-lg">Pronto para ajudar</h3>
          <p class="text-slate-400 dark:text-slate-500 text-sm mt-2 max-w-sm">
            Faça uma pergunta ou carregue um PDF para começar a análise com o agente selecionado.
          </p>
        </div>

        <!-- Message list -->
        <template v-for="(msg, i) in chat.messages" :key="i">
          <!-- User message -->
          <div v-if="msg.role === 'user'" class="flex justify-end">
            <div class="max-w-[70%] flex flex-col items-end gap-1">
              <!-- Player da gravação (quando veio de áudio) -->
              <div v-if="msg.audioUrl" class="bg-indigo-600 rounded-2xl rounded-tr-sm px-3 py-2">
                <audio controls preload="auto" class="h-8 w-48 accent-white" :src="msg.audioUrl" />
              </div>
              <!-- Texto (transcrição ou mensagem digitada) -->
              <div
                class="bg-indigo-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm"
                style="white-space: pre-wrap"
              >
                {{ msg.content }}
              </div>
            </div>
          </div>

          <!-- Assistant message -->
          <div v-else class="flex justify-start">
            <div class="flex gap-3 max-w-[80%]">
              <div
                class="w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-sm flex-shrink-0 mt-0.5"
              >
                🤖
              </div>
              <div class="flex flex-col gap-1">
                <div
                  class="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-slate-800 dark:text-slate-100 shadow-sm"
                  style="white-space: pre-wrap"
                >
                  {{ msg.content }}
                </div>
                <!-- Player TTS (quando o agente respondeu em áudio) -->
                <div v-if="msg.audioUrl" class="pl-1">
                  <audio controls preload="auto" class="h-8 w-48" :src="msg.audioUrl" />
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- Loading / step indicator -->
        <div v-if="chat.isLoading" class="flex justify-start">
          <div class="flex gap-3 max-w-[80%]">
            <div
              class="w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-sm flex-shrink-0 mt-0.5"
            >
              🤖
            </div>
            <div class="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl rounded-tl-sm px-4 py-3 text-sm shadow-sm">
              <div v-if="chat.currentStep" class="text-slate-500 dark:text-slate-400 italic text-xs">
                {{ chat.currentStep }}
              </div>
              <div v-else class="flex gap-1 items-center">
                <span
                  v-for="n in 3"
                  :key="n"
                  class="w-2 h-2 bg-slate-400 dark:bg-slate-500 rounded-full animate-bounce"
                  :style="{ animationDelay: `${(n - 1) * 0.15}s` }"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Input bar -->
      <div class="border-t border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-6 py-4">
        <!-- Indicador de gravação -->
        <div v-if="isRecording" class="flex items-center gap-3 mb-3">
          <span class="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse flex-shrink-0" />
          <span class="text-sm text-slate-600 dark:text-slate-300">
            Gravando... {{ formatRecordingTime(recordingSeconds) }}
          </span>
          <button
            @click="stopRecording"
            class="ml-auto flex-shrink-0 bg-red-500 hover:bg-red-600 text-white rounded-xl px-4 py-2 text-sm font-medium transition-colors"
          >
            Parar e Enviar
          </button>
        </div>

        <div v-else class="flex gap-3 items-end">
          <textarea
            v-model="input"
            @keydown="handleKeydown"
            placeholder="Digite sua pergunta... (Enter para enviar, Shift+Enter para nova linha)"
            rows="1"
            :disabled="chat.isLoading"
            class="flex-1 resize-none bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-600 rounded-xl px-4 py-3 text-sm text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent disabled:opacity-50 transition-all"
            style="max-height: 120px; overflow-y: auto"
          />
          <!-- Botão microfone -->
          <button
            @click="startRecording"
            :disabled="chat.isLoading"
            title="Gravar mensagem de voz"
            class="flex-shrink-0 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 disabled:opacity-40 text-slate-600 dark:text-slate-300 rounded-xl px-4 py-3 text-sm transition-colors"
          >
            🎤
          </button>
          <button
            @click="handleSend"
            :disabled="!input.trim() || chat.isLoading"
            class="flex-shrink-0 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white rounded-xl px-5 py-3 text-sm font-medium transition-colors"
          >
            Enviar
          </button>
        </div>
        <p class="text-slate-400 dark:text-slate-500 text-xs mt-2">
          Agente: <strong>{{ agentsStore.agents.find((a) => String(a.id) === chat.selectedAgentId)?.nome ?? chat.selectedAgentId }}</strong>
          <span v-if="chat.conversaId" class="ml-2 text-slate-500">&bull; Conversa #{{ chat.conversaId }}</span>
        </p>
      </div>
    </div>
  </div>
</template>
