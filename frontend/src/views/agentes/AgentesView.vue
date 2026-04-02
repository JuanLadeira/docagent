<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api, type Agente, type McpServer, type TelegramInstancia, type TelegramInstanciaCreate } from '@/api/client'
import { useAgentsStore } from '@/stores/agents'

const router = useRouter()
const agentsStore = useAgentsStore()

const aba = ref<'agentes' | 'telegram'>('agentes')

// ── Skills ────────────────────────────────────────────────────────────────────

const AVAILABLE_SKILLS = [
  { key: 'rag_search', label: 'Busca em Documentos', icon: '🔍' },
  { key: 'web_search', label: 'Busca na Web', icon: '🌐' },
  { key: 'human_handoff', label: 'Transferência Humana', icon: '🙋' },
]

const mcpServidores = ref<McpServer[]>([])

async function carregarMcpServidores() {
  try {
    const r = await api.listMcpServidores()
    mcpServidores.value = r.data.filter(s => s.tools.length > 0)
  } catch { /* MCP é opcional */ }
}

function labelMcpSkill(key: string) {
  const parts = key.split(':')
  if (parts.length !== 3) return key
  const [, sid, toolName] = parts
  const server = mcpServidores.value.find(s => String(s.id) === sid)
  return server ? `${server.nome} / ${toolName}` : toolName
}

// ── Agentes ───────────────────────────────────────────────────────────────────

const agentes = ref<Agente[]>([])
const loadingAgentes = ref(false)
const errorAgentes = ref('')
const deleting = ref<number | null>(null)
const busca = ref('')

const agentesFiltrados = computed(() => {
  const q = busca.value.trim().toLowerCase()
  if (!q) return agentes.value
  return agentes.value.filter(a =>
    a.nome.toLowerCase().includes(q) || a.descricao.toLowerCase().includes(q)
  )
})

async function loadAgentes() {
  loadingAgentes.value = true
  errorAgentes.value = ''
  try {
    const res = await api.listAgentes()
    agentes.value = res.data
  } catch {
    errorAgentes.value = 'Erro ao carregar agentes'
  } finally {
    loadingAgentes.value = false
  }
}

async function removeAgente(id: number) {
  if (!confirm('Remover este agente?')) return
  deleting.value = id
  try {
    await api.deleteAgente(id)
    agentes.value = agentes.value.filter(a => a.id !== id)
    agentsStore.invalidate()
  } catch {
    errorAgentes.value = 'Erro ao remover agente'
  } finally {
    deleting.value = null
  }
}

// ── Telegram ──────────────────────────────────────────────────────────────────

const instancias = ref<TelegramInstancia[]>([])
const loadingTelegram = ref(false)
const errorTelegram = ref('')
const configurando = ref<number | null>(null)

// Modal criar bot
const showCreateBot = ref(false)
const savingBot = ref(false)
const formBot = ref<TelegramInstanciaCreate>({ bot_token: '', agente_id: null, cria_atendimentos: true })

// Modal trocar agente
const editandoInstancia = ref<TelegramInstancia | null>(null)
const editAgenteId = ref<number | null>(null)
const editSaving = ref(false)

async function loadTelegram() {
  loadingTelegram.value = true
  errorTelegram.value = ''
  try {
    const res = await api.listTelegramInstancias()
    instancias.value = res.data
  } catch {
    errorTelegram.value = 'Erro ao carregar bots'
  } finally {
    loadingTelegram.value = false
  }
}

function openCreateBot() {
  formBot.value = { bot_token: '', agente_id: null, cria_atendimentos: true }
  showCreateBot.value = true
}

async function criarBot() {
  if (!formBot.value.bot_token.trim()) return
  savingBot.value = true
  errorTelegram.value = ''
  try {
    const res = await api.createTelegramInstancia(formBot.value)
    instancias.value.push(res.data)
    showCreateBot.value = false
  } catch (e: unknown) {
    errorTelegram.value = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Erro ao cadastrar bot'
  } finally {
    savingBot.value = false
  }
}

async function configurarWebhook(inst: TelegramInstancia) {
  configurando.value = inst.id
  try {
    const res = await api.configurarTelegramWebhook(inst.id)
    const idx = instancias.value.findIndex(i => i.id === inst.id)
    if (idx !== -1) instancias.value[idx] = res.data
  } catch {
    errorTelegram.value = 'Erro ao reconfigurar webhook'
  } finally {
    configurando.value = null
  }
}

async function removerBot(inst: TelegramInstancia) {
  const nome = inst.bot_username ? `@${inst.bot_username}` : `#${inst.id}`
  if (!confirm(`Remover bot ${nome}?`)) return
  try {
    await api.deleteTelegramInstancia(inst.id)
    instancias.value = instancias.value.filter(i => i.id !== inst.id)
  } catch {
    errorTelegram.value = 'Erro ao remover bot'
  }
}

function openEditAgente(inst: TelegramInstancia) {
  editandoInstancia.value = inst
  editAgenteId.value = inst.agente_id
}

async function salvarAgente() {
  if (!editandoInstancia.value) return
  editSaving.value = true
  try {
    const res = await api.updateTelegramInstancia(editandoInstancia.value.id, { agente_id: editAgenteId.value })
    const idx = instancias.value.findIndex(i => i.id === res.data.id)
    if (idx !== -1) instancias.value[idx] = res.data
    editandoInstancia.value = null
  } finally {
    editSaving.value = false
  }
}

function agenteName(agente_id: number | null): string {
  if (!agente_id) return '—'
  const a = agentsStore.agents.find(a => Number(a.id) === agente_id)
  return a?.nome ?? `#${agente_id}`
}

// ── Init ──────────────────────────────────────────────────────────────────────

onMounted(() => {
  loadAgentes()
  loadTelegram()
  carregarMcpServidores()
  agentsStore.fetchIfNeeded()
})
</script>

<template>
  <div class="h-full flex flex-col overflow-hidden bg-slate-50 dark:bg-slate-900">

    <!-- Header -->
    <div class="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-8 pt-6 pb-0">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h1 class="text-slate-800 dark:text-slate-100 text-xl font-bold">Agentes</h1>
          <p class="text-slate-500 dark:text-slate-400 text-sm mt-0.5">Gerencie agentes e bots de atendimento</p>
        </div>
        <button
          v-if="aba === 'agentes'"
          @click="router.push('/agentes/novo')"
          class="bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          + Novo agente
        </button>
        <button
          v-else
          @click="openCreateBot"
          class="bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          + Novo bot
        </button>
      </div>

      <!-- Abas -->
      <div class="flex gap-1">
        <button
          @click="aba = 'agentes'"
          class="px-4 py-2 text-sm font-medium border-b-2 transition-colors"
          :class="aba === 'agentes'
            ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400'
            : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'"
        >
          🤖 Agentes
          <span class="ml-1.5 text-xs px-1.5 py-0.5 rounded-full"
            :class="aba === 'agentes' ? 'bg-indigo-100 dark:bg-indigo-900/50 text-indigo-600 dark:text-indigo-300' : 'bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400'">
            {{ agentes.length }}
          </span>
        </button>
        <button
          @click="aba = 'telegram'"
          class="px-4 py-2 text-sm font-medium border-b-2 transition-colors"
          :class="aba === 'telegram'
            ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400'
            : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'"
        >
          ✈️ Bots Telegram
          <span class="ml-1.5 text-xs px-1.5 py-0.5 rounded-full"
            :class="aba === 'telegram' ? 'bg-indigo-100 dark:bg-indigo-900/50 text-indigo-600 dark:text-indigo-300' : 'bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400'">
            {{ instancias.length }}
          </span>
        </button>
      </div>
    </div>

    <!-- ── ABA: AGENTES ──────────────────────────────────────────────────────── -->
    <div v-if="aba === 'agentes'" class="flex-1 overflow-y-auto px-8 py-6">

      <!-- Busca -->
      <div class="relative mb-4">
        <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">🔍</span>
        <input
          v-model="busca"
          type="text"
          placeholder="Buscar agente por nome ou descrição..."
          class="w-full pl-9 pr-4 py-2.5 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-400 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500"
        />
      </div>

      <div v-if="errorAgentes" class="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 text-sm rounded-lg px-4 py-3 mb-4">
        {{ errorAgentes }}
      </div>

      <div v-if="loadingAgentes" class="text-slate-400 text-sm text-center py-12">Carregando...</div>

      <div v-else-if="agentesFiltrados.length === 0 && busca" class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-10 text-center">
        <p class="text-slate-400 text-sm">Nenhum agente encontrado para "<strong>{{ busca }}</strong>"</p>
      </div>

      <div v-else-if="agentes.length === 0" class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-12 text-center">
        <div class="text-4xl mb-3">🤖</div>
        <h3 class="text-slate-700 dark:text-slate-200 font-semibold">Nenhum agente cadastrado</h3>
        <p class="text-slate-400 dark:text-slate-500 text-sm mt-2">Crie o primeiro agente para começar.</p>
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="agente in agentesFiltrados"
          :key="agente.id"
          class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5 flex items-start gap-4"
        >
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
              <span class="text-slate-800 dark:text-slate-100 font-semibold">{{ agente.nome }}</span>
              <span
                class="px-2 py-0.5 rounded text-xs font-medium"
                :class="agente.ativo ? 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400' : 'bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400'"
              >
                {{ agente.ativo ? 'Ativo' : 'Inativo' }}
              </span>
            </div>
            <p class="text-slate-500 dark:text-slate-400 text-sm mb-2">{{ agente.descricao }}</p>
            <div class="flex flex-wrap gap-1.5">
              <span
                v-for="skill in agente.skill_names"
                :key="skill"
                class="px-2 py-0.5 bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-300 text-xs rounded font-medium"
              >
                <template v-if="skill.startsWith('mcp:')">
                  🔌 {{ labelMcpSkill(skill) }}
                </template>
                <template v-else>
                  {{ AVAILABLE_SKILLS.find(s => s.key === skill)?.icon }}
                  {{ AVAILABLE_SKILLS.find(s => s.key === skill)?.label ?? skill }}
                </template>
              </span>
              <span v-if="agente.skill_names.length === 0" class="text-xs text-slate-400 italic">sem ferramentas</span>
            </div>
            <p v-if="agente.system_prompt" class="text-slate-400 dark:text-slate-500 text-xs mt-2 italic truncate">
              Papel: {{ agente.system_prompt.slice(0, 80) }}{{ agente.system_prompt.length > 80 ? '...' : '' }}
            </p>
          </div>
          <div class="flex gap-2 flex-shrink-0">
            <button
              @click="router.push(`/agentes/${agente.id}/editar`)"
              class="px-3 py-1.5 text-sm text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
            >
              Editar
            </button>
            <button
              @click="removeAgente(agente.id)"
              :disabled="deleting === agente.id"
              class="px-3 py-1.5 text-sm text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors disabled:opacity-50"
            >
              {{ deleting === agente.id ? '...' : 'Remover' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── ABA: TELEGRAM ─────────────────────────────────────────────────────── -->
    <div v-else class="flex-1 overflow-y-auto px-8 py-6">

      <div v-if="errorTelegram" class="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 text-sm rounded-lg px-4 py-3 mb-4">
        {{ errorTelegram }}
      </div>

      <div v-if="loadingTelegram" class="text-slate-400 text-sm text-center py-12">Carregando...</div>

      <div v-else-if="instancias.length === 0" class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-12 text-center">
        <div class="text-4xl mb-3">✈️</div>
        <h3 class="text-slate-700 dark:text-slate-200 font-semibold">Nenhum bot cadastrado</h3>
        <p class="text-slate-400 dark:text-slate-500 text-sm mt-2">Crie um bot no @BotFather e cadastre o token aqui.</p>
        <button
          @click="openCreateBot"
          class="mt-4 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          + Novo bot
        </button>
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="inst in instancias"
          :key="inst.id"
          class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5 flex items-center gap-4"
        >
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
              <span class="font-mono font-semibold text-slate-800 dark:text-slate-100">
                {{ inst.bot_username ? `@${inst.bot_username}` : `Bot #${inst.id}` }}
              </span>
              <span
                class="px-2 py-0.5 rounded text-xs font-medium"
                :class="inst.status === 'ATIVA' ? 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400' : 'bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400'"
              >
                {{ inst.status }}
              </span>
              <span
                class="px-2 py-0.5 rounded text-xs font-medium"
                :class="inst.webhook_configured ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400' : 'bg-yellow-50 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400'"
              >
                {{ inst.webhook_configured ? '✓ webhook' : '⚠ webhook pendente' }}
              </span>
            </div>
            <div class="flex items-center gap-3 text-sm text-slate-500 dark:text-slate-400">
              <span>Agente: <strong class="text-slate-700 dark:text-slate-200">{{ agenteName(inst.agente_id) }}</strong></span>
              <span class="text-slate-300 dark:text-slate-600">·</span>
              <span>{{ inst.cria_atendimentos ? 'Cria atendimentos' : 'Resposta direta' }}</span>
            </div>
          </div>
          <div class="flex gap-2 flex-shrink-0">
            <button
              @click="openEditAgente(inst)"
              class="px-3 py-1.5 text-sm text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-700 rounded-lg hover:bg-indigo-50 dark:hover:bg-indigo-900/30 transition-colors"
            >
              Trocar agente
            </button>
            <button
              @click="configurarWebhook(inst)"
              :disabled="configurando === inst.id"
              class="px-3 py-1.5 text-sm text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors disabled:opacity-50"
            >
              {{ configurando === inst.id ? '...' : 'Reconfigurar' }}
            </button>
            <button
              @click="removerBot(inst)"
              class="px-3 py-1.5 text-sm text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors"
            >
              Remover
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Modal: criar bot ──────────────────────────────────────────────────── -->
    <div
      v-if="showCreateBot"
      class="fixed inset-0 z-50 flex items-center justify-center p-4"
      style="background: rgba(0,0,0,0.5)"
      @click.self="showCreateBot = false"
    >
      <div class="bg-white dark:bg-slate-800 rounded-xl shadow-xl w-full max-w-md p-6">
        <h2 class="font-semibold text-slate-800 dark:text-slate-100 mb-1">Novo Bot Telegram</h2>
        <p class="text-slate-500 dark:text-slate-400 text-xs mb-5">
          Crie um bot via <span class="font-mono">@BotFather</span> → <span class="font-mono">/newbot</span> e cole o token abaixo.
        </p>

        <div class="space-y-4">
          <div>
            <label class="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Token do Bot *</label>
            <input
              v-model="formBot.bot_token"
              type="password"
              placeholder="123456:ABCdefGHIjklMNOpqrSTUvwxYZ"
              class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <p class="text-xs text-slate-400 dark:text-slate-500 mt-1">O token não ficará visível após salvar.</p>
          </div>

          <div>
            <label class="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Agente responsável</label>
            <select
              v-model="formBot.agente_id"
              class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option :value="null">— Nenhum (não responde automaticamente) —</option>
              <option v-for="a in agentsStore.agents" :key="a.id" :value="Number(a.id)">
                {{ a.nome }}
              </option>
            </select>
          </div>

          <div class="flex items-center gap-3">
            <label class="relative inline-flex items-center cursor-pointer">
              <input v-model="formBot.cria_atendimentos" type="checkbox" class="sr-only peer" />
              <div class="w-10 h-5 bg-slate-200 dark:bg-slate-600 rounded-full peer peer-checked:bg-indigo-500 peer-checked:after:translate-x-5 after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all"></div>
            </label>
            <div>
              <p class="text-sm font-medium text-slate-700 dark:text-slate-200">Criar atendimentos</p>
              <p class="text-xs text-slate-400 dark:text-slate-500">
                {{ formBot.cria_atendimentos ? 'Mensagens entram na fila de atendimentos' : 'Bot responde diretamente, sem criar fila' }}
              </p>
            </div>
          </div>
        </div>

        <div class="flex justify-end gap-3 mt-6">
          <button @click="showCreateBot = false" class="px-4 py-2 text-sm text-slate-600 dark:text-slate-300 hover:text-slate-800 dark:hover:text-white transition-colors">
            Cancelar
          </button>
          <button
            @click="criarBot"
            :disabled="savingBot || !formBot.bot_token.trim()"
            class="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors bg-indigo-600 hover:bg-indigo-500"
          >
            {{ savingBot ? 'Cadastrando...' : 'Cadastrar' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── Modal: trocar agente do bot ──────────────────────────────────────── -->
    <div
      v-if="editandoInstancia"
      class="fixed inset-0 z-50 flex items-center justify-center p-4"
      style="background: rgba(0,0,0,0.5)"
      @click.self="editandoInstancia = null"
    >
      <div class="bg-white dark:bg-slate-800 rounded-xl shadow-xl w-full max-w-sm p-6">
        <h2 class="font-semibold text-slate-800 dark:text-slate-100 mb-1">Trocar agente</h2>
        <p class="text-slate-500 dark:text-slate-400 text-sm mb-4">
          {{ editandoInstancia.bot_username ? `@${editandoInstancia.bot_username}` : `Bot #${editandoInstancia.id}` }}
        </p>
        <select
          v-model="editAgenteId"
          class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 mb-5"
        >
          <option :value="null">— Nenhum (não responde automaticamente) —</option>
          <option v-for="a in agentsStore.agents" :key="a.id" :value="Number(a.id)">
            {{ a.nome }}
          </option>
        </select>
        <div class="flex justify-end gap-3">
          <button @click="editandoInstancia = null" class="px-4 py-2 text-sm text-slate-600 dark:text-slate-300 hover:text-slate-800 dark:hover:text-white transition-colors">
            Cancelar
          </button>
          <button
            @click="salvarAgente"
            :disabled="editSaving"
            class="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors bg-indigo-600 hover:bg-indigo-500"
          >
            {{ editSaving ? 'Salvando...' : 'Salvar' }}
          </button>
        </div>
      </div>
    </div>

  </div>
</template>
