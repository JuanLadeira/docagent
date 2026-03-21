<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useAgentsStore } from '@/stores/agents'

const chat = useChatStore()
const agentsStore = useAgentsStore()

const input = ref('')
const messagesEl = ref<HTMLElement | null>(null)
const fileInputEl = ref<HTMLInputElement | null>(null)
const isUploading = ref(false)

onMounted(() => agentsStore.fetchIfNeeded())

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

async function handleFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  isUploading.value = true
  await chat.uploadDocument(file)
  isUploading.value = false
  if (fileInputEl.value) fileInputEl.value.value = ''
}

function triggerUpload() {
  fileInputEl.value?.click()
}

function selectAgent(id: string) {
  chat.selectedAgentId = id
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
              <div class="text-xs mt-0.5 opacity-70">
                {{ agent.skills.map((s) => s.icon + ' ' + s.label).join(' · ') }}
              </div>
            </button>
          </div>
        </div>

        <!-- File upload -->
        <div>
          <label class="block text-slate-400 text-xs uppercase tracking-wider mb-2">
            Documentos
          </label>
          <input
            ref="fileInputEl"
            type="file"
            accept=".pdf"
            class="hidden"
            @change="handleFileChange"
          />
          <button
            @click="triggerUpload"
            :disabled="isUploading"
            class="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm text-slate-300 border border-slate-600 hover:border-slate-400 hover:text-white transition-colors disabled:opacity-50"
          >
            <span>{{ isUploading ? '⏳' : '📎' }}</span>
            <span>{{ isUploading ? 'Indexando...' : 'Carregar PDF' }}</span>
          </button>

          <div
            v-if="chat.uploadFeedback"
            class="mt-2 text-xs px-2 py-1 rounded"
            :class="
              chat.uploadFeedback.startsWith('⚠️')
                ? 'bg-red-900/40 text-red-400'
                : 'bg-green-900/40 text-green-400'
            "
          >
            {{ chat.uploadFeedback }}
            <span v-if="chat.lastUploadedFile" class="block text-slate-500 truncate">
              {{ chat.lastUploadedFile }}
            </span>
          </div>
        </div>

        <!-- Sessao -->
        <div>
          <label class="block text-slate-400 text-xs uppercase tracking-wider mb-2">Sessão</label>
          <div class="text-slate-500 text-xs font-mono mb-2">
            {{ chat.sessionId.slice(0, 8) }}...
          </div>
          <button
            @click="chat.resetSession()"
            :disabled="chat.isLoading"
            class="w-full text-left px-3 py-2 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-slate-700 transition-colors disabled:opacity-50"
          >
            🗑️ Nova conversa
          </button>
        </div>
      </div>

      <!-- Skills info -->
      <div class="p-4 border-t border-slate-700">
        <div class="text-slate-500 text-xs">
          <div v-if="agentsStore.agents.find((a) => a.id === chat.selectedAgentId)" class="space-y-1">
            <div
              v-for="skill in agentsStore.agents.find((a) => a.id === chat.selectedAgentId)?.skills"
              :key="skill.name"
              class="flex items-center gap-2"
            >
              <span>{{ skill.icon }}</span>
              <span>{{ skill.label }}</span>
            </div>
          </div>
        </div>
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
