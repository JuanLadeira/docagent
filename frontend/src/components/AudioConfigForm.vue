<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { audioApi, type AudioConfigUpdate } from '@/api/audioClient'

const props = defineProps<{
  agenteId?: number | null
}>()

const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const success = ref(false)
const error = ref('')
const isAgentOverride = ref(false)

const form = ref<AudioConfigUpdate>({
  stt_habilitado: false,
  stt_provider: 'faster_whisper',
  stt_modelo: 'base',
  tts_habilitado: false,
  tts_provider: 'piper',
  piper_voz: 'pt_BR-faber-medium',
  openai_tts_voz: 'nova',
  elevenlabs_voice_id: null,
  elevenlabs_api_key: null,
  modo_resposta: 'audio_e_texto',
})

const STT_PROVIDERS = [
  { value: 'faster_whisper', label: 'Faster Whisper (local)' },
  { value: 'openai', label: 'OpenAI Whisper API' },
]

const TTS_PROVIDERS = [
  { value: 'piper', label: 'Piper (local)' },
  { value: 'openai', label: 'OpenAI TTS API' },
  { value: 'elevenlabs', label: 'ElevenLabs' },
]

const MODO_RESPOSTA = [
  { value: 'audio_e_texto', label: 'Áudio e texto' },
  { value: 'audio_apenas', label: 'Somente áudio' },
  { value: 'texto_apenas', label: 'Somente texto' },
]

const OPENAI_TTS_VOICES = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']

const WHISPER_MODELS = ['tiny', 'base', 'small', 'medium', 'large-v3']

async function load() {
  loading.value = true
  error.value = ''
  try {
    const cfg = props.agenteId
      ? await audioApi.getAgente(props.agenteId)
      : await audioApi.getDefault()

    // is_agent_override vem do backend: true só quando o agente tem config própria
    isAgentOverride.value = cfg.is_agent_override

    form.value = {
      stt_habilitado: cfg.stt_habilitado,
      stt_provider: cfg.stt_provider,
      stt_modelo: cfg.stt_modelo,
      tts_habilitado: cfg.tts_habilitado,
      tts_provider: cfg.tts_provider,
      piper_voz: cfg.piper_voz,
      openai_tts_voz: cfg.openai_tts_voz,
      elevenlabs_voice_id: cfg.elevenlabs_voice_id,
      elevenlabs_api_key: null, // never pre-filled
      modo_resposta: cfg.modo_resposta,
    }
  } catch {
    error.value = 'Erro ao carregar configuração de áudio'
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  success.value = false
  error.value = ''
  try {
    if (props.agenteId) {
      await audioApi.saveAgente(props.agenteId, form.value)
      isAgentOverride.value = true
    } else {
      await audioApi.saveDefault(form.value)
    }
    success.value = true
    setTimeout(() => { success.value = false }, 3000)
  } catch {
    error.value = 'Erro ao salvar configuração de áudio'
  } finally {
    saving.value = false
  }
}

async function removeOverride() {
  if (!props.agenteId) return
  deleting.value = true
  error.value = ''
  try {
    await audioApi.deleteAgente(props.agenteId)
    isAgentOverride.value = false
    await load()
  } catch {
    error.value = 'Erro ao remover configuração'
  } finally {
    deleting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
    <div class="flex items-center justify-between mb-5">
      <div>
        <h2 class="text-slate-700 dark:text-slate-200 font-semibold text-sm uppercase tracking-wide">
          Configuração de Áudio
        </h2>
        <p v-if="agenteId" class="text-xs text-slate-400 dark:text-slate-500 mt-1">
          <span v-if="isAgentOverride" class="text-indigo-500 dark:text-indigo-400 font-medium">Configuração específica deste agente</span>
          <span v-else>Usando configuração padrão do tenant (editável abaixo)</span>
        </p>
      </div>
      <button
        v-if="agenteId && isAgentOverride"
        type="button"
        @click="removeOverride"
        :disabled="deleting"
        class="text-xs text-red-400 hover:text-red-600 dark:hover:text-red-300 transition-colors disabled:opacity-50"
      >
        {{ deleting ? 'Removendo...' : 'Usar padrão do tenant' }}
      </button>
    </div>

    <div v-if="loading" class="text-slate-400 dark:text-slate-500 text-sm py-4">Carregando...</div>

    <form v-else @submit.prevent="save" class="space-y-6">

      <!-- STT Section -->
      <div class="space-y-3">
        <div class="flex items-center gap-3">
          <input
            id="stt_hab"
            type="checkbox"
            v-model="form.stt_habilitado"
            class="accent-indigo-600 w-4 h-4"
          />
          <label for="stt_hab" class="text-sm font-medium text-slate-700 dark:text-slate-200">
            Transcrição de voz (STT)
          </label>
        </div>

        <div v-if="form.stt_habilitado" class="pl-7 space-y-3">
          <div>
            <label class="block text-slate-500 dark:text-slate-400 text-xs mb-1">Provider</label>
            <select
              v-model="form.stt_provider"
              class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-400"
            >
              <option v-for="p in STT_PROVIDERS" :key="p.value" :value="p.value">{{ p.label }}</option>
            </select>
          </div>

          <div v-if="form.stt_provider === 'faster_whisper'">
            <label class="block text-slate-500 dark:text-slate-400 text-xs mb-1">Modelo Whisper</label>
            <select
              v-model="form.stt_modelo"
              class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-400"
            >
              <option v-for="m in WHISPER_MODELS" :key="m" :value="m">{{ m }}</option>
            </select>
            <p class="text-xs text-slate-400 dark:text-slate-500 mt-1">
              Modelos maiores são mais precisos, mas mais lentos e consomem mais RAM.
            </p>
          </div>

          <div v-if="form.stt_provider === 'openai'">
            <label class="block text-slate-500 dark:text-slate-400 text-xs mb-1">Modelo</label>
            <input
              v-model="form.stt_modelo"
              placeholder="whisper-1"
              class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>
        </div>
      </div>

      <div class="border-t border-slate-100 dark:border-slate-700" />

      <!-- TTS Section -->
      <div class="space-y-3">
        <div class="flex items-center gap-3">
          <input
            id="tts_hab"
            type="checkbox"
            v-model="form.tts_habilitado"
            class="accent-indigo-600 w-4 h-4"
          />
          <label for="tts_hab" class="text-sm font-medium text-slate-700 dark:text-slate-200">
            Síntese de voz (TTS)
          </label>
        </div>

        <div v-if="form.tts_habilitado" class="pl-7 space-y-3">
          <div>
            <label class="block text-slate-500 dark:text-slate-400 text-xs mb-1">Provider</label>
            <select
              v-model="form.tts_provider"
              class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-400"
            >
              <option v-for="p in TTS_PROVIDERS" :key="p.value" :value="p.value">{{ p.label }}</option>
            </select>
          </div>

          <!-- Piper -->
          <div v-if="form.tts_provider === 'piper'">
            <label class="block text-slate-500 dark:text-slate-400 text-xs mb-1">Voz Piper</label>
            <input
              v-model="form.piper_voz"
              placeholder="pt_BR-faber-medium"
              class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-400"
            />
            <p class="text-xs text-slate-400 dark:text-slate-500 mt-1">
              Nome do arquivo de modelo Piper sem extensão (ex: pt_BR-faber-medium).
            </p>
          </div>

          <!-- OpenAI TTS -->
          <div v-if="form.tts_provider === 'openai'">
            <label class="block text-slate-500 dark:text-slate-400 text-xs mb-1">Voz</label>
            <select
              v-model="form.openai_tts_voz"
              class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-400"
            >
              <option v-for="v in OPENAI_TTS_VOICES" :key="v" :value="v">{{ v }}</option>
            </select>
          </div>

          <!-- ElevenLabs -->
          <div v-if="form.tts_provider === 'elevenlabs'" class="space-y-2">
            <div>
              <label class="block text-slate-500 dark:text-slate-400 text-xs mb-1">Voice ID</label>
              <input
                v-model="form.elevenlabs_voice_id"
                placeholder="ID da voz no ElevenLabs"
                class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>
            <div>
              <label class="block text-slate-500 dark:text-slate-400 text-xs mb-1">API Key</label>
              <input
                v-model="form.elevenlabs_api_key"
                type="password"
                placeholder="Deixe em branco para não alterar"
                class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- Modo de resposta (só aparece quando pelo menos um dos dois está habilitado) -->
      <div v-if="form.stt_habilitado || form.tts_habilitado" class="border-t border-slate-100 dark:border-slate-700 pt-4">
        <label class="block text-slate-500 dark:text-slate-400 text-xs mb-1.5">Modo de resposta</label>
        <select
          v-model="form.modo_resposta"
          class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-400"
        >
          <option v-for="m in MODO_RESPOSTA" :key="m.value" :value="m.value">{{ m.label }}</option>
        </select>
        <p class="text-xs text-slate-400 dark:text-slate-500 mt-1">
          Define se o agente responde com áudio, texto ou ambos no WhatsApp/Telegram.
        </p>
      </div>

      <!-- Feedback -->
      <div v-if="success" class="text-green-600 dark:text-green-400 text-sm">
        Configuração salva com sucesso.
      </div>
      <div v-if="error" class="text-red-500 dark:text-red-400 text-sm">{{ error }}</div>

      <button
        type="submit"
        :disabled="saving"
        class="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium rounded-lg py-2.5 text-sm transition-colors"
      >
        {{ saving ? 'Salvando...' : (agenteId ? 'Salvar configuração do agente' : 'Salvar configuração padrão') }}
      </button>
    </form>
  </div>
</template>
