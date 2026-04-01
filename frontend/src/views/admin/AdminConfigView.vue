<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { adminApi, type LlmMode } from '@/api/adminClient'

const llmMode = ref<LlmMode>('local')
const loading = ref(true)
const saving = ref(false)
const saveSuccess = ref(false)
const saveError = ref('')

async function load() {
  loading.value = true
  try {
    const res = await adminApi.getSystemConfig()
    llmMode.value = (res.data.llm_mode as LlmMode) || 'local'
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function save() {
  saving.value = true
  saveSuccess.value = false
  saveError.value = ''
  try {
    await adminApi.updateSystemConfig({ llm_mode: llmMode.value })
    saveSuccess.value = true
    setTimeout(() => { saveSuccess.value = false }, 3000)
  } catch {
    saveError.value = 'Erro ao salvar configuração'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="p-8 max-w-2xl">
    <h1 class="text-slate-800 dark:text-slate-100 text-2xl font-bold mb-1">Configurações do Sistema</h1>
    <p class="text-slate-500 text-sm mb-8">Parâmetros globais que afetam todos os tenants</p>

    <div v-if="loading" class="text-slate-400 text-sm">Carregando...</div>

    <div v-else class="space-y-6">
      <!-- Modo LLM -->
      <div class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
        <h2 class="text-slate-700 dark:text-slate-200 font-semibold mb-1">Modo LLM</h2>
        <p class="text-slate-500 text-sm mb-5">
          Define se os agentes rodam com o modelo local (Ollama) ou se cada tenant deve fornecer sua própria chave de API.
        </p>

        <div class="space-y-3">
          <label
            class="flex items-start gap-3 p-4 rounded-lg border-2 cursor-pointer transition-colors"
            :class="llmMode === 'local'
              ? 'border-violet-500 bg-violet-50 dark:bg-violet-900/20'
              : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'"
          >
            <input type="radio" v-model="llmMode" value="local" class="mt-0.5 accent-violet-600" />
            <div>
              <div class="font-medium text-slate-800 dark:text-slate-100 text-sm">Local (Ollama)</div>
              <div class="text-slate-500 text-xs mt-0.5">
                Todos os tenants usam o modelo Ollama rodando no servidor. Nenhuma chave de API necessária.
              </div>
            </div>
          </label>

          <label
            class="flex items-start gap-3 p-4 rounded-lg border-2 cursor-pointer transition-colors"
            :class="llmMode === 'api'
              ? 'border-violet-500 bg-violet-50 dark:bg-violet-900/20'
              : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'"
          >
            <input type="radio" v-model="llmMode" value="api" class="mt-0.5 accent-violet-600" />
            <div>
              <div class="font-medium text-slate-800 dark:text-slate-100 text-sm">API (por tenant)</div>
              <div class="text-slate-500 text-xs mt-0.5">
                Cada tenant configura seu próprio provider e chave de API (OpenAI, Groq, Anthropic, Gemini).
                Tenants sem chave configurada fazem fallback para Ollama local.
              </div>
            </div>
          </label>
        </div>

        <div v-if="saveSuccess" class="mt-4 text-green-600 dark:text-green-400 text-sm">
          Configuração salva com sucesso.
        </div>
        <div v-if="saveError" class="mt-4 text-red-500 text-sm">{{ saveError }}</div>

        <button
          @click="save"
          :disabled="saving"
          class="mt-5 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          {{ saving ? 'Salvando...' : 'Salvar' }}
        </button>
      </div>

      <!-- Info sobre providers -->
      <div v-if="llmMode === 'api'" class="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-xl p-5">
        <h3 class="text-amber-800 dark:text-amber-300 font-medium text-sm mb-2">Modo API ativo</h3>
        <p class="text-amber-700 dark:text-amber-400 text-xs">
          No painel de Configurações, cada tenant owner pode escolher entre:
          <strong>OpenAI</strong>, <strong>Groq</strong>, <strong>Anthropic (Claude)</strong> e <strong>Google Gemini</strong>.
          Tenants que não configurarem continuarão usando o Ollama local como fallback.
        </p>
      </div>
    </div>
  </div>
</template>
