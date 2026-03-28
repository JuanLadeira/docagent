<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  api,
  subscribeAtendimentoEventos,
  subscribeAtendimentoLista,
  type Atendimento,
  type AtendimentoDetalhe,
  type MensagemAtendimento,
  type MensagemOrigem,
  type SseStatus,
  type WhatsappInstancia,
} from '@/api/client'

const router = useRouter()

const props = defineProps<{ canal: 'WHATSAPP' | 'TELEGRAM' }>()

// ── Estado ────────────────────────────────────────────────────────────────────

const ativos = ref<Atendimento[]>([])       // ATIVO + HUMANO
const historico = ref<Atendimento[]>([])    // ENCERRADO
const aba = ref<'ativos' | 'historico'>('ativos')
const carregandoHistorico = ref(false)

const selecionado = ref<AtendimentoDetalhe | null>(null)
const carregandoDetalhe = ref(false)
const mensagemInput = ref('')
const enviando = ref(false)
const mensagensContainer = ref<HTMLElement | null>(null)

let sseCleanupConversa: (() => void) | null = null
let sseCleanupLista: (() => void) | null = null

const sseStatus = ref<SseStatus>('connecting')

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
    await selecionar(r.data)
  } finally {
    criando.value = false
  }
}

// ── Modal: Adicionar contato ───────────────────────────────────────────────────

const showAdicionarContato = ref(false)
const contatoForm = ref({ nome: '', email: '', notas: '' })
const salvandoContato = ref(false)

function abrirAdicionarContato() {
  contatoForm.value = { nome: '', email: '', notas: '' }
  showAdicionarContato.value = true
}

async function confirmarAdicionarContato() {
  if (!selecionado.value || !contatoForm.value.nome.trim() || salvandoContato.value) return
  salvandoContato.value = true
  try {
    await api.criarContato({
      numero: selecionado.value.numero,
      nome: contatoForm.value.nome.trim(),
      email: contatoForm.value.email.trim() || null,
      notas: contatoForm.value.notas.trim() || null,
      instancia_id: selecionado.value.instancia_id ?? 0,
    })
    // Recarregar o atendimento para pegar o contato_id atualizado
    const r = await api.getAtendimento(selecionado.value.id)
    selecionado.value = r.data
    atualizarNaLista(r.data)
    showAdicionarContato.value = false
  } finally {
    salvandoContato.value = false
  }
}

// ── SSE lista ─────────────────────────────────────────────────────────────────

function iniciarSseLista() {
  sseCleanupLista?.()
  sseCleanupLista = subscribeAtendimentoLista(
    (event) => {
      const at = event.atendimento
      if (!at) return
      if (at.canal !== props.canal) return

      if (event.type === 'NOVO_ATENDIMENTO') {
        if (!ativos.value.find((a) => a.id === at.id)) {
          ativos.value.unshift(at)
        }
      } else if (event.type === 'ATENDIMENTO_ATUALIZADO') {
        if (at.status === 'ENCERRADO') {
          ativos.value = ativos.value.filter((a) => a.id !== at.id)
          if (!historico.value.find((a) => a.id === at.id)) {
            historico.value.unshift(at)
          }
          if (selecionado.value?.id === at.id) {
            selecionado.value.status = 'ENCERRADO'
          }
        } else {
          const idx = ativos.value.findIndex((a) => a.id === at.id)
          if (idx !== -1) {
            ativos.value[idx] = at
          }
          if (selecionado.value?.id === at.id) {
            selecionado.value.status = at.status
            selecionado.value.prioridade = at.prioridade
          }
        }
      }
    },
    async (status) => {
      const wasDisconnected = sseStatus.value !== 'connected'
      sseStatus.value = status
      // Ao reconectar após queda, recarrega a lista para não perder eventos perdidos
      if (status === 'connected' && wasDisconnected) {
        await carregarAtivos()
      }
    },
  )
}

// ── Carga inicial ─────────────────────────────────────────────────────────────

async function carregarAtivos() {
  try {
    const r = await api.listAtendimentos(undefined, props.canal)
    ativos.value = r.data.filter((a) => a.status !== 'ENCERRADO')
  } catch {
    // silencioso
  }
}

async function carregarHistorico() {
  if (carregandoHistorico.value) return
  carregandoHistorico.value = true
  try {
    const r = await api.listAtendimentos('ENCERRADO', props.canal)
    historico.value = r.data
  } catch {
    // silencioso
  } finally {
    carregandoHistorico.value = false
  }
}

// ── Seleção de atendimento ────────────────────────────────────────────────────

async function selecionar(atendimento: Atendimento) {
  sseCleanupConversa?.()
  sseCleanupConversa = null
  carregandoDetalhe.value = true
  selecionado.value = null

  try {
    const r = await api.getAtendimento(atendimento.id)
    selecionado.value = r.data
  } catch {
    carregandoDetalhe.value = false
    return
  } finally {
    carregandoDetalhe.value = false
  }

  await nextTick()
  scrollToBottom()

  sseCleanupConversa = subscribeAtendimentoEventos(atendimento.id, (event) => {
    if (event.type === 'NOVA_MENSAGEM' && selecionado.value?.id === atendimento.id) {
      const nova: MensagemAtendimento = {
        id: Date.now(),
        origem: event.origem as MensagemOrigem,
        conteudo: event.conteudo as string,
        created_at: (event.created_at as string) ?? new Date().toISOString(),
      }
      selecionado.value.mensagens.push(nova)
      nextTick(scrollToBottom)
    }
  })
}

function scrollToBottom() {
  if (mensagensContainer.value) {
    mensagensContainer.value.scrollTop = mensagensContainer.value.scrollHeight
  }
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
  sseCleanupConversa?.()
  sseCleanupConversa = null
  selecionado.value = null
}

async function enviarMensagem() {
  if (!selecionado.value || !mensagemInput.value.trim() || enviando.value) return
  enviando.value = true
  const conteudo = mensagemInput.value.trim()
  mensagemInput.value = ''
  try {
    await api.enviarMensagemOperador(selecionado.value.id, conteudo)
    // A mensagem chega via SSE (NOVA_MENSAGEM) — não adicionar aqui para evitar duplicata
  } catch {
    mensagemInput.value = conteudo
  } finally {
    enviando.value = false
  }
}

function atualizarNaLista(at: Atendimento) {
  const idx = ativos.value.findIndex((a) => a.id === at.id)
  if (idx !== -1) ativos.value[idx] = at
}

// ── Aba histórico ─────────────────────────────────────────────────────────────

async function mudarAba(novaAba: 'ativos' | 'historico') {
  aba.value = novaAba
  if (novaAba === 'historico' && historico.value.length === 0) {
    await carregarHistorico()
  }
}

// ── Helpers de exibição ───────────────────────────────────────────────────────

const listaExibida = computed(() => aba.value === 'ativos' ? ativos.value : historico.value)

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

function formatarData(iso: string) {
  return new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit' })
}

function badgePrioridade(prioridade: string) {
  if (prioridade === 'URGENTE') return 'bg-red-100 text-red-700'
  if (prioridade === 'ALTA') return 'bg-yellow-100 text-yellow-700'
  return null
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(async () => {
  await carregarAtivos()
  iniciarSseLista()
})

onUnmounted(() => {
  sseCleanupConversa?.()
  sseCleanupLista?.()
})
</script>

<template>
  <div class="flex h-full">
    <!-- Painel esquerdo: lista de atendimentos -->
    <aside class="w-64 flex-shrink-0 border-r border-gray-200 bg-white flex flex-col">
      <div class="p-4 border-b border-gray-200 flex items-center justify-between">
        <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide">
          {{ props.canal === 'WHATSAPP' ? 'WhatsApp' : 'Telegram' }}
        </h2>
        <button
          v-if="props.canal === 'WHATSAPP'"
          class="text-xs px-2 py-1 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
          @click="abrirNovaConversa"
        >
          + Nova
        </button>
      </div>

      <!-- Banner de status SSE -->
      <div
        v-if="sseStatus !== 'connected'"
        class="px-3 py-1.5 flex items-center gap-2 text-xs"
        :class="sseStatus === 'connecting' ? 'bg-yellow-50 text-yellow-700' : 'bg-red-50 text-red-700'"
      >
        <svg class="animate-spin h-3 w-3 flex-shrink-0" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
        </svg>
        {{ sseStatus === 'connecting' ? 'Conectando...' : 'Reconectando...' }}
      </div>

      <!-- Abas -->
      <div class="flex border-b border-gray-200">
        <button
          class="flex-1 py-2 text-xs font-medium transition-colors"
          :class="aba === 'ativos' ? 'border-b-2 border-indigo-600 text-indigo-600' : 'text-gray-500 hover:text-gray-700'"
          @click="mudarAba('ativos')"
        >
          Ativos
          <span v-if="ativos.length > 0" class="ml-1 bg-indigo-100 text-indigo-700 px-1.5 rounded-full text-xs">
            {{ ativos.length }}
          </span>
        </button>
        <button
          class="flex-1 py-2 text-xs font-medium transition-colors"
          :class="aba === 'historico' ? 'border-b-2 border-indigo-600 text-indigo-600' : 'text-gray-500 hover:text-gray-700'"
          @click="mudarAba('historico')"
        >
          Histórico
        </button>
      </div>

      <div class="flex-1 overflow-y-auto">
        <div v-if="carregandoHistorico" class="p-4 text-sm text-gray-400 text-center">
          Carregando...
        </div>
        <div v-else-if="listaExibida.length === 0" class="p-4 text-sm text-gray-500 text-center mt-8">
          {{ aba === 'ativos' ? 'Nenhum atendimento ativo' : 'Nenhum histórico' }}
        </div>

        <button
          v-for="at in listaExibida"
          :key="at.id"
          class="w-full text-left px-4 py-3 border-b border-gray-100 hover:bg-gray-50 transition-colors"
          :class="selecionado?.id === at.id ? 'bg-indigo-50' : ''"
          @click="selecionar(at)"
        >
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full flex-shrink-0" :class="corStatus(at.status)" />
            <div class="min-w-0">
              <div class="text-sm font-medium text-gray-800 truncate">
                {{ at.nome_contato || at.numero }}
              </div>
              <div v-if="at.nome_contato" class="text-xs text-gray-400 truncate">
                {{ at.numero }}
              </div>
            </div>
          </div>
          <div class="mt-0.5 flex items-center gap-1.5 pl-4 flex-wrap">
            <!-- Canal badge -->
            <span
              class="text-xs px-1.5 py-0.5 rounded font-medium"
              :class="at.canal === 'TELEGRAM'
                ? 'bg-blue-100 text-blue-700'
                : 'bg-green-100 text-green-700'"
            >
              {{ at.canal === 'TELEGRAM' ? 'TG' : 'WA' }}
            </span>
            <span
              class="text-xs px-1.5 py-0.5 rounded font-medium"
              :class="{
                'bg-green-100 text-green-700': at.status === 'ATIVO',
                'bg-orange-100 text-orange-700': at.status === 'HUMANO',
                'bg-gray-100 text-gray-500': at.status === 'ENCERRADO',
              }"
            >
              {{ at.status === 'HUMANO' ? 'Operador' : at.status === 'ATIVO' ? 'Bot' : 'Encerrado' }}
            </span>
            <span
              v-if="badgePrioridade(at.prioridade)"
              class="text-xs px-1.5 py-0.5 rounded font-medium"
              :class="badgePrioridade(at.prioridade)!"
            >
              {{ at.prioridade }}
            </span>
            <span v-if="aba === 'historico'" class="text-xs text-gray-400">
              {{ formatarData(at.updated_at) }}
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

    <!-- Modal: adicionar contato -->
    <div
      v-if="showAdicionarContato"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      @click.self="showAdicionarContato = false"
    >
      <div class="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <h3 class="text-base font-semibold text-gray-800 mb-1">Adicionar contato</h3>
        <p class="text-sm text-gray-500 mb-4">{{ selecionado?.numero }}</p>

        <div class="space-y-4">
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">Nome *</label>
            <input
              v-model="contatoForm.nome"
              type="text"
              placeholder="João Silva"
              class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">E-mail <span class="text-gray-400">(opcional)</span></label>
            <input
              v-model="contatoForm.email"
              type="email"
              placeholder="joao@email.com"
              class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">Notas <span class="text-gray-400">(opcional)</span></label>
            <textarea
              v-model="contatoForm.notas"
              rows="2"
              placeholder="Cliente VIP, prefere contato às manhãs..."
              class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            />
          </div>
        </div>

        <div class="flex justify-end gap-2 mt-5">
          <button
            class="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
            @click="showAdicionarContato = false"
          >
            Cancelar
          </button>
          <button
            class="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
            :disabled="salvandoContato || !contatoForm.nome.trim()"
            @click="confirmarAdicionarContato"
          >
            {{ salvandoContato ? 'Salvando...' : 'Salvar contato' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Painel direito: conversa -->
    <main class="flex-1 flex flex-col bg-gray-50">
      <!-- Carregando -->
      <div
        v-if="carregandoDetalhe"
        class="flex-1 flex items-center justify-center text-gray-400 text-sm gap-2"
      >
        <svg class="animate-spin h-4 w-4 text-indigo-500" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
        </svg>
        Carregando conversa...
      </div>

      <!-- Sem seleção -->
      <div
        v-else-if="!selecionado"
        class="flex-1 flex items-center justify-center text-gray-400 text-sm"
      >
        Selecione um atendimento
      </div>

      <template v-else-if="selecionado">
        <!-- Cabeçalho -->
        <div class="px-6 py-3 border-b border-gray-200 bg-white flex items-center justify-between">
          <div>
            <div class="font-semibold text-gray-800 flex items-center gap-2">
              <span>{{ selecionado.nome_contato || selecionado.numero }}</span>
              <span
                v-if="selecionado.prioridade !== 'NORMAL'"
                class="text-xs px-1.5 py-0.5 rounded font-medium"
                :class="badgePrioridade(selecionado.prioridade)!"
              >
                {{ selecionado.prioridade }}
              </span>
              <button
                v-if="selecionado.contato_id"
                class="text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600 hover:bg-indigo-100 transition-colors font-normal"
                @click="router.push(`/contatos/${selecionado.contato_id}`)"
              >
                Ver contato →
              </button>
            </div>
            <div class="text-xs text-gray-400 flex items-center gap-2">
              <span>{{ selecionado.numero }}</span>
              <button
                v-if="!selecionado.contato_id && selecionado.status !== 'ENCERRADO' && selecionado.canal !== 'TELEGRAM'"
                class="text-gray-400 hover:text-indigo-600 transition-colors"
                @click="abrirAdicionarContato"
              >
                + Adicionar contato
              </button>
            </div>
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
              v-if="selecionado.status !== 'ENCERRADO'"
              class="px-3 py-1.5 text-xs font-medium rounded-lg bg-red-100 text-red-700 hover:bg-red-200 transition-colors"
              @click="encerrar"
            >
              Encerrar
            </button>
          </div>
        </div>

        <!-- Mensagens -->
        <div ref="mensagensContainer" class="flex-1 overflow-y-auto p-4 flex flex-col gap-2">
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
