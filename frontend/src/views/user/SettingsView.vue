<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/api/client'
import WhatsappView from '@/views/whatsapp/WhatsappView.vue'
import TelegramView from '@/views/telegram/TelegramView.vue'
import McpServidoresView from '@/views/McpServidoresView.vue'
import AudioConfigForm from '@/components/AudioConfigForm.vue'

type SettingsTab = 'perfil' | 'whatsapp' | 'telegram' | 'mcp' | 'ia' | 'audio'

const auth = useAuthStore()
const abaAtiva = ref<SettingsTab>('perfil')

const tabs: { key: SettingsTab; label: string; icon: string; ownerOnly: boolean }[] = [
  { key: 'perfil', label: 'Perfil', icon: '👤', ownerOnly: false },
  { key: 'ia', label: 'IA', icon: '🤖', ownerOnly: true },
  { key: 'audio', label: 'Áudio', icon: '🎙️', ownerOnly: true },
  { key: 'whatsapp', label: 'WhatsApp', icon: '📱', ownerOnly: true },
  { key: 'telegram', label: 'Telegram', icon: '✈️', ownerOnly: true },
  { key: 'mcp', label: 'Servidores MCP', icon: '🔌', ownerOnly: true },
]

// ── IA / LLM Config ───────────────────────────────────────────────────────────
const llmProvider = ref('')
const llmModel = ref('')
const llmApiKey = ref('')
const llmApiKeySet = ref(false)
const llmLoading = ref(false)
const llmSaving = ref(false)
const llmSuccess = ref(false)
const llmError = ref('')

const PROVIDERS = [
  { value: '', label: 'Padrão do sistema' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'groq', label: 'Groq' },
  { value: 'anthropic', label: 'Anthropic (Claude)' },
  { value: 'gemini', label: 'Google Gemini' },
  { value: 'ollama', label: 'Ollama (local)' },
]

const MODEL_PLACEHOLDERS: Record<string, string> = {
  openai: 'gpt-4o-mini',
  groq: 'llama-3.1-8b-instant',
  anthropic: 'claude-3-haiku-20240307',
  gemini: 'gemini-1.5-flash',
  ollama: 'qwen2.5:7b',
}

async function loadLlmConfig() {
  llmLoading.value = true
  try {
    const res = await api.getLlmConfig()
    llmProvider.value = res.data.llm_provider ?? ''
    llmModel.value = res.data.llm_model ?? ''
    llmApiKeySet.value = res.data.llm_api_key_set
  } catch {
    // silencioso
  } finally {
    llmLoading.value = false
  }
}

async function saveLlmConfig() {
  llmSaving.value = true
  llmSuccess.value = false
  llmError.value = ''
  try {
    await api.updateLlmConfig({
      llm_provider: llmProvider.value || null,
      llm_model: llmModel.value || null,
      llm_api_key: llmApiKey.value || null,
    })
    llmSuccess.value = true
    llmApiKey.value = ''
    llmApiKeySet.value = true
    setTimeout(() => { llmSuccess.value = false }, 3000)
  } catch {
    llmError.value = 'Erro ao salvar configuração'
  } finally {
    llmSaving.value = false
  }
}

onMounted(() => {
  if (auth.isOwner) loadLlmConfig()
})

const currentPassword = ref('')
const newPassword = ref('')
const confirm = ref('')
const loading = ref(false)
const success = ref(false)
const error = ref('')

async function changePassword() {
  if (newPassword.value !== confirm.value) {
    error.value = 'As senhas não coincidem'
    return
  }
  loading.value = true
  error.value = ''
  success.value = false
  try {
    await api.changePassword(currentPassword.value, newPassword.value)
    success.value = true
    currentPassword.value = ''
    newPassword.value = ''
    confirm.value = ''
  } catch {
    error.value = 'Senha atual incorreta'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="h-full overflow-y-auto bg-slate-50 dark:bg-slate-900">
    <!-- Tab bar -->
    <div class="border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-8">
      <div class="flex gap-1">
        <button
          v-for="tab in tabs.filter(t => !t.ownerOnly || auth.isOwner)"
          :key="tab.key"
          @click="abaAtiva = tab.key"
          class="flex items-center gap-1.5 px-4 py-4 text-sm font-medium border-b-2 transition-colors"
          :class="
            abaAtiva === tab.key
              ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400'
              : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'
          "
        >
          <span>{{ tab.icon }}</span>
          <span>{{ tab.label }}</span>
        </button>
      </div>
    </div>

    <!-- Aba: Perfil -->
    <div v-show="abaAtiva === 'perfil'" class="p-8 max-w-lg">
      <!-- Perfil -->
      <div class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6 mb-6">
        <h2 class="text-slate-700 dark:text-slate-200 font-semibold mb-4">Perfil</h2>
        <div class="space-y-3 text-sm">
          <div class="flex gap-4">
            <span class="text-slate-400 dark:text-slate-500 w-24">Usuário</span>
            <span class="text-slate-700 dark:text-slate-200 font-medium">{{ auth.username }}</span>
          </div>
          <div class="flex gap-4">
            <span class="text-slate-400 dark:text-slate-500 w-24">Perfil</span>
            <span
              class="px-2 py-0.5 rounded text-xs font-medium"
              :class="auth.isOwner ? 'bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300' : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300'"
            >
              {{ auth.role }}
            </span>
          </div>
          <div class="flex gap-4">
            <span class="text-slate-400 dark:text-slate-500 w-24">Tenant ID</span>
            <span class="text-slate-700 dark:text-slate-200">{{ auth.tenantId }}</span>
          </div>
        </div>
      </div>

      <!-- Alterar senha -->
      <div class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
        <h2 class="text-slate-700 dark:text-slate-200 font-semibold mb-4">Alterar senha</h2>

        <div
          v-if="success"
          class="bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-400 text-sm rounded-lg px-4 py-3 mb-4"
        >
          Senha alterada com sucesso!
        </div>

        <form @submit.prevent="changePassword" class="space-y-3">
          <div>
            <label class="block text-slate-500 dark:text-slate-400 text-sm mb-1">Senha atual</label>
            <input
              v-model="currentPassword"
              type="password"
              required
              class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2.5 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>
          <div>
            <label class="block text-slate-500 dark:text-slate-400 text-sm mb-1">Nova senha</label>
            <input
              v-model="newPassword"
              type="password"
              required
              class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2.5 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>
          <div>
            <label class="block text-slate-500 dark:text-slate-400 text-sm mb-1">Confirmar nova senha</label>
            <input
              v-model="confirm"
              type="password"
              required
              class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2.5 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>

          <div v-if="error" class="text-red-500 dark:text-red-400 text-sm">{{ error }}</div>

          <button
            type="submit"
            :disabled="loading"
            class="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium rounded-lg py-2.5 text-sm transition-colors"
          >
            {{ loading ? 'Salvando...' : 'Alterar senha' }}
          </button>
        </form>
      </div>
    </div>

    <!-- Aba: IA -->
    <div v-show="abaAtiva === 'ia'" class="p-8 max-w-lg">
      <div class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
        <h2 class="text-slate-700 dark:text-slate-200 font-semibold mb-1">Configuração de LLM</h2>
        <p class="text-slate-500 dark:text-slate-400 text-sm mb-5">
          Escolha o provider e forneça sua chave de API para usar um modelo externo.
          Deixe em branco para usar o modelo configurado pelo administrador.
        </p>

        <div v-if="llmLoading" class="text-slate-400 text-sm">Carregando...</div>

        <form v-else @submit.prevent="saveLlmConfig" class="space-y-4">
          <div>
            <label class="block text-slate-500 dark:text-slate-400 text-sm mb-1">Provider</label>
            <select
              v-model="llmProvider"
              class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2.5 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-400"
            >
              <option v-for="p in PROVIDERS" :key="p.value" :value="p.value">{{ p.label }}</option>
            </select>
          </div>

          <div v-if="llmProvider && llmProvider !== 'ollama'">
            <label class="block text-slate-500 dark:text-slate-400 text-sm mb-1">Modelo</label>
            <input
              v-model="llmModel"
              :placeholder="MODEL_PLACEHOLDERS[llmProvider] || 'Nome do modelo'"
              class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2.5 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>

          <div v-if="llmProvider && llmProvider !== 'ollama'">
            <label class="block text-slate-500 dark:text-slate-400 text-sm mb-1">
              API Key
              <span v-if="llmApiKeySet" class="ml-1 text-xs text-green-600 dark:text-green-400">(configurada)</span>
            </label>
            <input
              v-model="llmApiKey"
              type="password"
              :placeholder="llmApiKeySet ? 'Deixe em branco para não alterar' : 'Sua chave de API'"
              class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2.5 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>

          <div v-if="llmSuccess" class="text-green-600 dark:text-green-400 text-sm">
            Configuração salva com sucesso.
          </div>
          <div v-if="llmError" class="text-red-500 dark:text-red-400 text-sm">{{ llmError }}</div>

          <button
            type="submit"
            :disabled="llmSaving"
            class="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium rounded-lg py-2.5 text-sm transition-colors"
          >
            {{ llmSaving ? 'Salvando...' : 'Salvar configuração' }}
          </button>
        </form>
      </div>
    </div>

    <!-- Aba: Áudio -->
    <div v-show="abaAtiva === 'audio'" class="p-8 max-w-lg">
      <p class="text-slate-500 dark:text-slate-400 text-sm mb-5">
        Configuração padrão de STT/TTS para todos os agentes do tenant.
        Pode ser sobrescrita individualmente em cada agente.
      </p>
      <div class="mb-4 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 text-amber-700 dark:text-amber-300 text-xs">
        Agentes com configuração própria (editável na página do agente) não são afetados por esta configuração padrão.
      </div>
      <AudioConfigForm />
    </div>

    <!-- Aba: WhatsApp -->
    <WhatsappView v-show="abaAtiva === 'whatsapp'" />

    <!-- Aba: Telegram -->
    <TelegramView v-show="abaAtiva === 'telegram'" />

    <!-- Aba: Servidores MCP -->
    <McpServidoresView v-show="abaAtiva === 'mcp'" />
  </div>
</template>
