<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import {
  api,
  subscribeAtendimentoEventos,
  type Atendimento,
  type AtendimentoDetalhe,
  type MensagemAtendimento,
  type MensagemOrigem,
  type WhatsappInstancia,
} from '@/api/client'

// ── Estado ────────────────────────────────────────────────────────────────────

const atendimentos = ref<Atendimento[]>([])
const selecionado = ref<AtendimentoDetalhe | null>(null)
const mensagemInput = ref('')
const enviando = ref(false)
let sseCleanup: (() => void) | null = null
let pollingInterval: ReturnType<typeof setInterval> | null = null

// ── Nova conversa ─────────────────────────────────────────────────────────────

const showNovaConversa = ref(false)
const instancias = ref<WhatsappInstancia[]>([])
const novaForm = ref({ instancia_id: 0, numero: '', mensagem_inicial: '' })
const criando = ref(false)

async function abrirNovaConversa() {
  try {
    const r = await api.listInstancias()
    instancias.value = r.data.filter((i) => i.status === 'CONECTADA')
    if (instancias.value.length > 0) novaForm.value.instancia_id = instancias.value[0].id
  } catch {
    // silencioso
  }
  novaForm.value.numero = ''
  novaForm.value.mensagem_inicial = ''
  showNovaConversa.value = true
}

async function confirmarNovaConversa() {
  if (!novaForm.value.instancia_id || !novaForm.value.numero.trim() || criando.value) return
  criando.value = true
  try {
    const r = await api.criarAtendimento({
      instancia_id: novaForm.value.instancia_id,
      numero: novaForm.value.numero.trim(),
      mensagem_inicial: novaForm.value.mensagem_inicial.trim() || undefined,
    })
    showNovaConversa.value = false
    await carregarLista()
    await selecionar(r.data)
  } finally {
    criando.value = false
  }
}

// ── Polling da lista ──────────────────────────────────────────────────────────

async function carregarLista() {
  try {
    const r = await api.listAtendimentos()
    atendimentos.value = r.data.filter((a) => a.status !== 'ENCERRADO')
  } catch {
    // silencioso
  }
}

// ── Seleção de atendimento ────────────────────────────────────────────────────

async function selecionar(atendimento: Atendimento) {
  // Cancelar SSE anterior
  sseCleanup?.()
  sseCleanup = null

  try {
    const r = await api.getAtendimento(atendimento.id)
    selecionado.value = r.data
  } catch {
    return
  }

  // Conectar SSE para novas mensagens
  sseCleanup = subscribeAtendimentoEventos(atendimento.id, (event) => {
    if (event.type === 'NOVA_MENSAGEM' && selecionado.value?.id === atendimento.id) {
      const nova: MensagemAtendimento = {
        id: Date.now(),
        origem: event.origem as MensagemOrigem,
        conteudo: event.conteudo as string,
        created_at: (event.created_at as string) ?? new Date().toISOString(),
      }
      selecionado.value.mensagens.push(nova)
    }
  })
}

// ── Ações de controle ─────────────────────────────────────────────────────────

async function assumir() {
  if (!selecionado.value) return
  const r = await api.assumirAtendimento(selecionado.value.id)
  selecionado.value.status = r.data.status
  atualizarNaLista(r.data)
}

async function devolver() {
  if (!selecionado.value) return
  const r = await api.devolverAtendimento(selecionado.value.id)
  selecionado.value.status = r.data.status
  atualizarNaLista(r.data)
}

async function encerrar() {
  if (!selecionado.value) return
  await api.encerrarAtendimento(selecionado.value.id)
  atendimentos.value = atendimentos.value.filter((a) => a.id !== selecionado.value!.id)
  sseCleanup?.()
  sseCleanup = null
  selecionado.value = null
}

async function enviarMensagem() {
  if (!selecionado.value || !mensagemInput.value.trim() || enviando.value) return
  enviando.value = true
  try {
    const r = await api.enviarMensagemOperador(selecionado.value.id, mensagemInput.value.trim())
    selecionado.value.mensagens.push(r.data)
    mensagemInput.value = ''
  } finally {
    enviando.value = false
  }
}

function atualizarNaLista(at: Atendimento) {
  const idx = atendimentos.value.findIndex((a) => a.id === at.id)
  if (idx !== -1) atendimentos.value[idx] = { ...atendimentos.value[idx], status: at.status }
}

// ── Helpers de exibição ───────────────────────────────────────────────────────

function corStatus(status: string) {
  if (status === 'ATIVO') return 'bg-green-500'
  if (status === 'HUMANO') return 'bg-orange-500'
  return 'bg-gray-400'
}

function classBolha(origem: MensagemOrigem) {
  if (origem === 'CONTATO') return 'self-start bg-gray-200 text-gray-800'
  if (origem === 'AGENTE') return 'self-end bg-indigo-600 text-white'
  return 'self-end bg-green-600 text-white'
}

function labelOrigem(origem: MensagemOrigem) {
  if (origem === 'CONTATO') return 'Contato'
  if (origem === 'AGENTE') return 'Agente'
  return 'Operador'
}

function formatarHora(iso: string) {
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(async () => {
  await carregarLista()
  pollingInterval = setInterval(carregarLista, 5000)
})

onUnmounted(() => {
  sseCleanup?.()
  if (pollingInterval) clearInterval(pollingInterval)
})
</script>

<template>
  <div class="flex h-full">
    <!-- Painel esquerdo: lista de atendimentos -->
    <aside class="w-64 flex-shrink-0 border-r border-gray-200 bg-white flex flex-col">
      <div class="p-4 border-b border-gray-200 flex items-center justify-between">
        <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide">Atendimentos</h2>
        <button
          class="text-xs px-2 py-1 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
          @click="abrirNovaConversa"
        >
          + Nova
        </button>
      </div>

      <div class="flex-1 overflow-y-auto">
        <div v-if="atendimentos.length === 0" class="p-4 text-sm text-gray-500 text-center mt-8">
          Nenhum atendimento ativo
        </div>

        <button
          v-for="at in atendimentos"
          :key="at.id"
          class="w-full text-left px-4 py-3 border-b border-gray-100 hover:bg-gray-50 transition-colors"
          :class="selecionado?.id === at.id ? 'bg-indigo-50' : ''"
          @click="selecionar(at)"
        >
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full flex-shrink-0" :class="corStatus(at.status)" />
            <span class="text-sm font-medium text-gray-800 truncate">
              {{ at.nome_contato || at.numero }}
            </span>
          </div>
          <div class="mt-0.5 flex items-center gap-2 pl-4">
            <span
              class="text-xs px-1.5 py-0.5 rounded font-medium"
              :class="{
                'bg-green-100 text-green-700': at.status === 'ATIVO',
                'bg-orange-100 text-orange-700': at.status === 'HUMANO',
              }"
            >
              {{ at.status }}
            </span>
          </div>
        </button>
      </div>
    </aside>

    <!-- Modal: nova conversa -->
    <div
      v-if="showNovaConversa"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      @click.self="showNovaConversa = false"
    >
      <div class="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <h3 class="text-base font-semibold text-gray-800 mb-4">Nova conversa</h3>

        <div class="space-y-4">
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">Instância WhatsApp</label>
            <select
              v-model="novaForm.instancia_id"
              class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option v-for="i in instancias" :key="i.id" :value="i.id">
                {{ i.instance_name }}
              </option>
            </select>
            <p v-if="instancias.length === 0" class="mt-1 text-xs text-red-500">
              Nenhuma instância conectada
            </p>
          </div>

          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">Número (com DDI e DDD)</label>
            <input
              v-model="novaForm.numero"
              type="text"
              placeholder="5511999999999"
              class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">
              Mensagem inicial <span class="text-gray-400">(opcional)</span>
            </label>
            <textarea
              v-model="novaForm.mensagem_inicial"
              rows="3"
              placeholder="Olá! Como posso ajudar?"
              class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            />
          </div>
        </div>

        <div class="flex justify-end gap-2 mt-5">
          <button
            class="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
            @click="showNovaConversa = false"
          >
            Cancelar
          </button>
          <button
            class="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
            :disabled="criando || !novaForm.numero.trim() || instancias.length === 0"
            @click="confirmarNovaConversa"
          >
            {{ criando ? 'Iniciando...' : 'Iniciar conversa' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Painel direito: conversa -->
    <main class="flex-1 flex flex-col bg-gray-50">
      <!-- Sem seleção -->
      <div
        v-if="!selecionado"
        class="flex-1 flex items-center justify-center text-gray-400 text-sm"
      >
        Selecione um atendimento
      </div>

      <template v-else>
        <!-- Cabeçalho -->
        <div class="px-6 py-3 border-b border-gray-200 bg-white flex items-center justify-between">
          <div>
            <div class="font-semibold text-gray-800">
              {{ selecionado.nome_contato || selecionado.numero }}
            </div>
            <div class="text-xs text-gray-500">{{ selecionado.numero }}</div>
          </div>

          <!-- Botões de controle -->
          <div class="flex gap-2">
            <button
              v-if="selecionado.status === 'ATIVO'"
              class="px-3 py-1.5 text-xs font-medium rounded-lg bg-orange-100 text-orange-700 hover:bg-orange-200 transition-colors"
              @click="assumir"
            >
              Assumir
            </button>
            <button
              v-if="selecionado.status === 'HUMANO'"
              class="px-3 py-1.5 text-xs font-medium rounded-lg bg-indigo-100 text-indigo-700 hover:bg-indigo-200 transition-colors"
              @click="devolver"
            >
              Devolver ao Agente
            </button>
            <button
              class="px-3 py-1.5 text-xs font-medium rounded-lg bg-red-100 text-red-700 hover:bg-red-200 transition-colors"
              @click="encerrar"
            >
              Encerrar
            </button>
          </div>
        </div>

        <!-- Mensagens -->
        <div class="flex-1 overflow-y-auto p-4 flex flex-col gap-2">
          <div
            v-for="msg in selecionado.mensagens"
            :key="msg.id"
            class="flex flex-col max-w-[70%]"
            :class="msg.origem === 'CONTATO' ? 'self-start' : 'self-end'"
          >
            <span class="text-xs text-gray-400 mb-0.5 px-1">
              {{ labelOrigem(msg.origem) }} · {{ formatarHora(msg.created_at) }}
            </span>
            <div
              class="px-4 py-2.5 rounded-2xl text-sm leading-relaxed"
              :class="classBolha(msg.origem)"
            >
              {{ msg.conteudo }}
            </div>
          </div>

          <div v-if="selecionado.mensagens.length === 0" class="text-center text-gray-400 text-sm mt-8">
            Nenhuma mensagem ainda
          </div>
        </div>

        <!-- Input do operador (só quando HUMANO) -->
        <div
          v-if="selecionado.status === 'HUMANO'"
          class="px-4 py-3 border-t border-gray-200 bg-white flex gap-2"
        >
          <input
            v-model="mensagemInput"
            type="text"
            placeholder="Digite sua mensagem..."
            class="flex-1 px-4 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            @keyup.enter="enviarMensagem"
          />
          <button
            class="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
            :disabled="enviando || !mensagemInput.trim()"
            @click="enviarMensagem"
          >
            Enviar
          </button>
        </div>
      </template>
    </main>
  </div>
</template>
