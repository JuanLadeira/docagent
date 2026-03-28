<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api, type TelegramInstancia, type TelegramInstanciaCreate } from '@/api/client'
import { useAgentsStore } from '@/stores/agents'

const agentsStore = useAgentsStore()
const instancias = ref<TelegramInstancia[]>([])
const loading = ref(false)
const error = ref('')
const configurando = ref<number | null>(null)

// Modal criação
const showCreateModal = ref(false)
const saving = ref(false)
const form = ref<TelegramInstanciaCreate>({ bot_token: '', agente_id: null, cria_atendimentos: true })

onMounted(() => Promise.all([load(), agentsStore.fetchIfNeeded()]))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.listTelegramInstancias()
    instancias.value = res.data
  } catch {
    error.value = 'Erro ao carregar bots'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.value = { bot_token: '', agente_id: null, cria_atendimentos: true }
  showCreateModal.value = true
}

async function criar() {
  if (!form.value.bot_token.trim()) return
  saving.value = true
  error.value = ''
  try {
    const res = await api.createTelegramInstancia(form.value)
    instancias.value.push(res.data)
    showCreateModal.value = false
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Erro ao cadastrar bot'
  } finally {
    saving.value = false
  }
}

async function configurarWebhook(inst: TelegramInstancia) {
  configurando.value = inst.id
  try {
    const res = await api.configurarTelegramWebhook(inst.id)
    const idx = instancias.value.findIndex((i) => i.id === inst.id)
    if (idx !== -1) instancias.value[idx] = res.data
  } catch {
    error.value = 'Erro ao reconfigurar webhook'
  } finally {
    configurando.value = null
  }
}

async function remover(inst: TelegramInstancia) {
  const nome = inst.bot_username ? `@${inst.bot_username}` : `#${inst.id}`
  if (!confirm(`Remover bot ${nome}?`)) return
  try {
    await api.deleteTelegramInstancia(inst.id)
    instancias.value = instancias.value.filter((i) => i.id !== inst.id)
  } catch {
    error.value = 'Erro ao remover bot'
  }
}

function agenteName(agente_id: number | null): string {
  if (!agente_id) return '—'
  const a = agentsStore.agents.find((a) => Number(a.id) === agente_id)
  return a?.name ?? `#${agente_id}`
}
</script>

<template>
  <div class="h-full overflow-y-auto p-8" style="background: #f8fafc">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-xl font-bold text-slate-800">Telegram</h1>
        <p class="text-slate-500 text-sm mt-0.5">Gerencie bots de atendimento via Telegram</p>
      </div>
      <button
        @click="openCreate"
        class="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors"
        style="background: #6366f1"
      >
        <span>+</span> Novo bot
      </button>
    </div>

    <!-- Erro -->
    <div v-if="error" class="mb-4 px-4 py-3 rounded-lg bg-red-50 text-red-700 text-sm">
      {{ error }}
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-slate-500 text-sm">Carregando...</div>

    <!-- Tabela -->
    <div v-else-if="instancias.length > 0" class="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-slate-100 text-left">
            <th class="px-5 py-3 text-slate-500 font-medium">Bot</th>
            <th class="px-5 py-3 text-slate-500 font-medium">Agente</th>
            <th class="px-5 py-3 text-slate-500 font-medium">Cria Atendimentos</th>
            <th class="px-5 py-3 text-slate-500 font-medium">Webhook</th>
            <th class="px-5 py-3 text-slate-500 font-medium">Status</th>
            <th class="px-5 py-3 text-slate-500 font-medium">Ações</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="inst in instancias"
            :key="inst.id"
            class="border-b border-slate-50 hover:bg-slate-50 transition-colors"
          >
            <td class="px-5 py-3 font-mono text-slate-700">
              {{ inst.bot_username ? `@${inst.bot_username}` : `#${inst.id}` }}
            </td>
            <td class="px-5 py-3 text-slate-600">{{ agenteName(inst.agente_id) }}</td>
            <td class="px-5 py-3">
              <span
                class="px-2.5 py-1 rounded-full text-xs font-medium"
                :class="inst.cria_atendimentos
                  ? 'bg-green-100 text-green-700'
                  : 'bg-slate-100 text-slate-500'"
              >
                {{ inst.cria_atendimentos ? 'Sim' : 'Não' }}
              </span>
            </td>
            <td class="px-5 py-3">
              <span
                class="px-2.5 py-1 rounded-full text-xs font-medium"
                :class="inst.webhook_configured
                  ? 'bg-green-100 text-green-700'
                  : 'bg-yellow-100 text-yellow-700'"
              >
                {{ inst.webhook_configured ? '✓ Configurado' : '⚠ Pendente' }}
              </span>
            </td>
            <td class="px-5 py-3">
              <span
                class="px-2.5 py-1 rounded-full text-xs font-medium"
                :class="inst.status === 'ATIVA'
                  ? 'bg-green-900 text-green-300'
                  : 'bg-red-900 text-red-300'"
              >
                {{ inst.status }}
              </span>
            </td>
            <td class="px-5 py-3">
              <div class="flex items-center gap-2">
                <button
                  @click="configurarWebhook(inst)"
                  :disabled="configurando === inst.id"
                  class="px-3 py-1 rounded text-xs font-medium text-indigo-600 hover:bg-indigo-50 disabled:opacity-50 transition-colors"
                >
                  {{ configurando === inst.id ? '...' : 'Reconfigurar' }}
                </button>
                <button
                  @click="remover(inst)"
                  class="px-3 py-1 rounded text-xs font-medium text-red-500 hover:bg-red-50 transition-colors"
                >
                  Remover
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Vazio -->
    <div v-else class="flex flex-col items-center justify-center py-20 text-center">
      <div class="text-5xl mb-4">✈️</div>
      <p class="text-slate-600 font-medium">Nenhum bot cadastrado</p>
      <p class="text-slate-400 text-sm mt-1">Crie um bot no @BotFather e cadastre o token aqui</p>
      <button
        @click="openCreate"
        class="mt-5 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors"
        style="background: #6366f1"
      >
        + Novo bot
      </button>
    </div>

    <!-- ── Modal: cadastrar bot ───────────────────────────────────────────── -->
    <div
      v-if="showCreateModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4"
      style="background: rgba(0,0,0,0.5)"
    >
      <div class="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <h2 class="font-semibold text-slate-800 mb-1">Novo Bot Telegram</h2>
        <p class="text-slate-500 text-xs mb-5">
          Crie um bot via <span class="font-mono">@BotFather</span> → <span class="font-mono">/newbot</span> e cole o token abaixo.
        </p>

        <div class="space-y-4">
          <div>
            <label class="block text-xs font-medium text-slate-600 mb-1">Token do Bot</label>
            <input
              v-model="form.bot_token"
              type="password"
              placeholder="123456:ABCdefGHIjklMNOpqrSTUvwxYZ"
              class="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <p class="text-xs text-slate-400 mt-1">O token não ficará visível após salvar.</p>
          </div>

          <div>
            <label class="block text-xs font-medium text-slate-600 mb-1">Agente responsável</label>
            <select
              v-model="form.agente_id"
              class="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option :value="null">— Nenhum (não responde automaticamente) —</option>
              <option v-for="a in agentsStore.agents" :key="a.id" :value="Number(a.id)">
                {{ a.name }}
              </option>
            </select>
          </div>

          <div class="flex items-center gap-3">
            <label class="relative inline-flex items-center cursor-pointer">
              <input
                v-model="form.cria_atendimentos"
                type="checkbox"
                class="sr-only peer"
              />
              <div class="w-10 h-5 bg-slate-200 rounded-full peer peer-checked:bg-indigo-500 peer-checked:after:translate-x-5 after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all"></div>
            </label>
            <div>
              <p class="text-sm font-medium text-slate-700">Criar atendimentos</p>
              <p class="text-xs text-slate-400">
                {{ form.cria_atendimentos
                  ? 'Mensagens entram na fila de atendimentos'
                  : 'Bot responde diretamente, sem criar fila' }}
              </p>
            </div>
          </div>
        </div>

        <div class="flex justify-end gap-3 mt-6">
          <button
            @click="showCreateModal = false"
            class="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 transition-colors"
          >
            Cancelar
          </button>
          <button
            @click="criar"
            :disabled="saving || !form.bot_token.trim()"
            class="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors"
            style="background: #6366f1"
          >
            {{ saving ? 'Cadastrando...' : 'Cadastrar' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
