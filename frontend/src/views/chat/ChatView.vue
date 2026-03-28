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

onMounted(async () => {
  await agentsStore.fetchIfNeeded()
  if (chat.selectedAgentId) loadDocumentos(chat.selectedAgentId)
})

watch(() => chat.selectedAgentId, (id) => {
  if (id) loadDocumentos(id)
})

// Scroll ao fim quando chegam novas mensagens ou step muda
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
</script>

<template>
  <div class="flex h-full" style="background: #f8fafc">
    <!-- ─── Sidebar ─────────────────────────────────────────────────────── -->
    <aside class="w-72 flex-shrink-0 flex flex-col border-r border-slate-200" style="background: #0f172a">
      <!-- Header -->
      <div class="p-5 border-b border-slate-700">
        <h2 class="text-white font-semibold text-sm">Painel do Agente</h2>
      </div>

      <div class="flex-1 p-4 space-y-5 overflow-y-auto">
        <!-- Agent selector -->
        <div>
          <label class="block text-slate-400 text-xs uppercase tracking-wider mb-2">Agente</label>
          <div v-if="agentsStore.isFetching" class="text-slate-500 text-xs">Carregando...</div>
          <div v-else-if="agentsStore.agents.length === 0" class="text-slate-500 text-xs">
            Nenhum agente disponível
          </div>
          <div v-else class="space-y-1">
            <button
              v-for="agent in agentsStore.agents"
              :key="agent.id"
              @click="selectAgent(agent.id)"
              class="w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors"
              :class="
                chat.selectedAgentId === agent.id
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-300 hover:bg-slate-700'
              "
            >
              <div class="font-medium">{{ agent.name }}</div>
              <div class="text-xs mt-0.5 opacity-70 flex flex-wrap gap-x-2">
                <span v-for="skill in agent.skills" :key="skill.name">
                  {{ skill.icon }} {{ skill.label }}
                </span>
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

          <!-- Sem agente selecionado -->
          <div v-if="!chat.selectedAgentId" class="text-slate-500 text-xs py-1">
            Selecione um agente para ver seus documentos.
          </div>

          <!-- Carregando -->
          <div v-else-if="loadingDocs" class="text-slate-500 text-xs py-1">
            Carregando...
          </div>

          <!-- Lista de documentos -->
          <div v-else class="space-y-1">
            <div
              v-for="doc in documentos"
              :key="doc.id"
              class="flex items-center justify-between gap-2 px-2 py-1.5 rounded-lg bg-slate-800 group"
            >
              <div class="min-w-0 flex-1">
                <div class="text-slate-300 text-xs font-medium truncate" :title="doc.filename">
                  📄 {{ doc.filename }}
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

            <!-- Estado vazio -->
            <div v-if="documentos.length === 0" class="text-slate-500 text-xs py-1">
              Nenhum documento indexado.
              <button @click="triggerUpload" class="text-indigo-400 hover:text-indigo-300 underline ml-1">
                Adicionar PDF
              </button>
            </div>
          </div>

          <!-- Upload em progresso -->
          <div v-if="isUploading" class="mt-2 flex items-center gap-2 text-xs text-slate-400">
            <span class="inline-block w-3 h-3 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></span>
            Indexando...
          </div>

          <!-- Erro -->
          <div v-if="docError" class="mt-2 text-xs text-red-400 bg-red-900/30 px-2 py-1 rounded">
            {{ docError }}
          </div>
        </div>

      </div>

      <!-- Nova conversa -->
      <div class="p-4 border-t border-slate-700">
        <button
          @click="chat.resetSession()"
          :disabled="chat.isLoading"
          class="w-full text-left px-3 py-2 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-slate-700 transition-colors disabled:opacity-50"
        >
          🗑️ Nova conversa
        </button>
      </div>
    </aside>

    <!-- ─── Main chat area ─────────────────────────────────────────────── -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- Messages -->
      <div ref="messagesEl" class="flex-1 overflow-y-auto p-6 space-y-4">
        <!-- Empty state -->
        <div
          v-if="chat.messages.length === 0 && !chat.isLoading"
          class="flex flex-col items-center justify-center h-full text-center"
        >
          <div class="text-6xl mb-4">📄</div>
          <h3 class="text-slate-700 font-semibold text-lg">Pronto para ajudar</h3>
          <p class="text-slate-400 text-sm mt-2 max-w-sm">
            Faça uma pergunta ou carregue um PDF para começar a análise com o agente selecionado.
          </p>
        </div>

        <!-- Message list -->
        <template v-for="(msg, i) in chat.messages" :key="i">
          <!-- User message -->
          <div v-if="msg.role === 'user'" class="flex justify-end">
            <div
              class="max-w-[70%] bg-indigo-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm"
              style="white-space: pre-wrap"
            >
              {{ msg.content }}
            </div>
          </div>

          <!-- Assistant message -->
          <div v-else class="flex justify-start">
            <div class="flex gap-3 max-w-[80%]">
              <div
                class="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-sm flex-shrink-0 mt-0.5"
              >
                🤖
              </div>
              <div
                class="bg-white border border-slate-200 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-slate-800 shadow-sm"
                style="white-space: pre-wrap"
              >
                {{ msg.content }}
              </div>
            </div>
          </div>
        </template>

        <!-- Loading / step indicator -->
        <div v-if="chat.isLoading" class="flex justify-start">
          <div class="flex gap-3 max-w-[80%]">
            <div
              class="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-sm flex-shrink-0 mt-0.5"
            >
              🤖
            </div>
            <div class="bg-white border border-slate-200 rounded-2xl rounded-tl-sm px-4 py-3 text-sm shadow-sm">
              <div v-if="chat.currentStep" class="text-slate-500 italic text-xs">
                {{ chat.currentStep }}
              </div>
              <div v-else class="flex gap-1 items-center">
                <span
                  v-for="n in 3"
                  :key="n"
                  class="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
                  :style="{ animationDelay: `${(n - 1) * 0.15}s` }"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Input bar -->
      <div class="border-t border-slate-200 bg-white px-6 py-4">
        <div class="flex gap-3 items-end">
          <textarea
            v-model="input"
            @keydown="handleKeydown"
            placeholder="Digite sua pergunta... (Enter para enviar, Shift+Enter para nova linha)"
            rows="1"
            :disabled="chat.isLoading"
            class="flex-1 resize-none bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-800 placeholder-slate-400 outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent disabled:opacity-50 transition-all"
            style="max-height: 120px; overflow-y: auto"
          />
          <button
            @click="handleSend"
            :disabled="!input.trim() || chat.isLoading"
            class="flex-shrink-0 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white rounded-xl px-5 py-3 text-sm font-medium transition-colors"
          >
            Enviar
          </button>
        </div>
        <p class="text-slate-400 text-xs mt-2">
          Agente: <strong>{{ agentsStore.agents.find((a) => a.id === chat.selectedAgentId)?.name ?? chat.selectedAgentId }}</strong>
        </p>
      </div>
    </div>
  </div>
</template>
