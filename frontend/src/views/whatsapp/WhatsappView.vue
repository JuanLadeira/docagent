<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import {
  api,
  subscribeInstanciaEventos,
  type WhatsappInstancia,
  type InstanciaCreate,
} from '@/api/client'
import { useAgentsStore } from '@/stores/agents'

const agentsStore = useAgentsStore()
const instancias = ref<WhatsappInstancia[]>([])
const loading = ref(false)
const error = ref('')

// Modal criação
const showCreateModal = ref(false)
const saving = ref(false)
const form = ref<InstanciaCreate>({ instance_name: '', agente_id: null })

// Modal QR code
const showQrModal = ref(false)
const qrBase64 = ref<string | null>(null)
const qrInstanciaId = ref<number | null>(null)
let sseCleanup: (() => void) | null = null

const STATUS_STYLE: Record<WhatsappInstancia['status'], string> = {
  CRIADA: 'bg-slate-700 text-slate-300',
  CONECTANDO: 'bg-yellow-900 text-yellow-300',
  CONECTADA: 'bg-green-900 text-green-300',
  DESCONECTADA: 'bg-red-900 text-red-300',
}

onMounted(() => Promise.all([load(), agentsStore.fetchIfNeeded()]))
onUnmounted(() => sseCleanup?.())

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.listInstancias()
    instancias.value = res.data
  } catch {
    error.value = 'Erro ao carregar instâncias'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.value = { instance_name: '', agente_id: null }
  showCreateModal.value = true
}

async function criar() {
  if (!form.value.instance_name.trim()) return
  saving.value = true
  error.value = ''
  try {
    const res = await api.createInstancia(form.value)
    instancias.value.push(res.data)
    showCreateModal.value = false
  } catch {
    error.value = 'Erro ao criar instância'
  } finally {
    saving.value = false
  }
}

async function conectar(instancia: WhatsappInstancia) {
  qrInstanciaId.value = instancia.id
  qrBase64.value = null
  showQrModal.value = true

  // SSE primeiro — garante que QRCODE_UPDATED não é perdido por race condition
  sseCleanup?.()
  sseCleanup = subscribeInstanciaEventos(instancia.id, (event) => {
    if (event.type === 'QRCODE_UPDATED' && event.qr_base64) {
      qrBase64.value = event.qr_base64 as string
    } else if (event.type === 'CONNECTION_UPDATE' && event.status) {
      const status = event.status as WhatsappInstancia['status']
      atualizarStatus(instancia.id, status)
      if (status === 'CONECTADA') fecharQrModal()
    }
  })

  // Pequeno delay para o subscribe HTTP ser processado antes de disparar o QR
  await new Promise(resolve => setTimeout(resolve, 200))

  try {
    const res = await api.getQrcode(instancia.id)
    if (res.data.base64) {
      qrBase64.value = res.data.base64
    }
    atualizarStatus(instancia.id, 'CONECTANDO')
  } catch {
    // SSE ainda receberá QRCODE_UPDATED se chegar via webhook
  }
}

function fecharQrModal() {
  sseCleanup?.()
  sseCleanup = null
  showQrModal.value = false
  qrBase64.value = null
  qrInstanciaId.value = null
}

function atualizarStatus(id: number, status: WhatsappInstancia['status']) {
  const idx = instancias.value.findIndex((i) => i.id === id)
  if (idx !== -1) instancias.value[idx] = { ...instancias.value[idx], status }
}

async function sincronizar(instancia: WhatsappInstancia) {
  try {
    const res = await api.sincronizarStatus(instancia.id)
    const idx = instancias.value.findIndex((i) => i.id === instancia.id)
    if (idx !== -1) instancias.value[idx] = res.data
  } catch {
    // silencioso
  }
}

async function remover(instancia: WhatsappInstancia) {
  if (!confirm(`Remover instância "${instancia.instance_name}"?`)) return
  try {
    await api.deleteInstancia(instancia.id)
    instancias.value = instancias.value.filter((i) => i.id !== instancia.id)
  } catch {
    error.value = 'Erro ao remover instância'
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
        <h1 class="text-xl font-bold text-slate-800">WhatsApp</h1>
        <p class="text-slate-500 text-sm mt-0.5">Gerencie instâncias de atendimento via WhatsApp</p>
      </div>
      <button
        @click="openCreate"
        class="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors"
        style="background: #6366f1"
      >
        <span>+</span> Nova instância
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
            <th class="px-5 py-3 text-slate-500 font-medium">Instância</th>
            <th class="px-5 py-3 text-slate-500 font-medium">Agente</th>
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
            <td class="px-5 py-3 font-mono text-slate-700">{{ inst.instance_name }}</td>
            <td class="px-5 py-3 text-slate-600">{{ agenteName(inst.agente_id) }}</td>
            <td class="px-5 py-3">
              <span
                class="px-2.5 py-1 rounded-full text-xs font-medium"
                :class="STATUS_STYLE[inst.status]"
              >
                {{ inst.status }}
              </span>
            </td>
            <td class="px-5 py-3">
              <div class="flex items-center gap-2">
                <button
                  @click="conectar(inst)"
                  class="px-3 py-1 rounded text-xs font-medium text-indigo-600 hover:bg-indigo-50 transition-colors"
                >
                  Conectar
                </button>
                <button
                  @click="sincronizar(inst)"
                  class="px-3 py-1 rounded text-xs font-medium text-slate-500 hover:bg-slate-100 transition-colors"
                >
                  Sincronizar
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
    <div
      v-else
      class="flex flex-col items-center justify-center py-20 text-center"
    >
      <div class="text-5xl mb-4">📱</div>
      <p class="text-slate-600 font-medium">Nenhuma instância cadastrada</p>
      <p class="text-slate-400 text-sm mt-1">Crie uma instância para começar a atender no WhatsApp</p>
      <button
        @click="openCreate"
        class="mt-5 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors"
        style="background: #6366f1"
      >
        + Nova instância
      </button>
    </div>

    <!-- ── Modal: criar instância ────────────────────────────────────────── -->
    <div
      v-if="showCreateModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4"
      style="background: rgba(0,0,0,0.5)"
    >
      <div class="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <h2 class="font-semibold text-slate-800 mb-5">Nova instância WhatsApp</h2>

        <div class="space-y-4">
          <div>
            <label class="block text-xs font-medium text-slate-600 mb-1">Nome da instância</label>
            <input
              v-model="form.instance_name"
              type="text"
              placeholder="ex: minha-empresa"
              class="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <p class="text-xs text-slate-400 mt-1">Sem espaços. Será o identificador no Evolution API.</p>
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
            :disabled="saving || !form.instance_name.trim()"
            class="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors"
            style="background: #6366f1"
          >
            {{ saving ? 'Criando...' : 'Criar' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── Modal: QR Code ────────────────────────────────────────────────── -->
    <div
      v-if="showQrModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4"
      style="background: rgba(0,0,0,0.5)"
    >
      <div class="bg-white rounded-xl shadow-xl w-full max-w-sm p-6 text-center">
        <h2 class="font-semibold text-slate-800 mb-1">Conectar WhatsApp</h2>
        <p class="text-slate-500 text-sm mb-5">Escaneie o QR code com o celular</p>

        <!-- QR carregando -->
        <div
          v-if="!qrBase64"
          class="w-56 h-56 mx-auto flex items-center justify-center rounded-xl border-2 border-dashed border-slate-200"
        >
          <div class="text-slate-400 text-sm">Aguardando QR code...</div>
        </div>

        <!-- QR disponível -->
        <img
          v-else
          :src="qrBase64"
          alt="QR Code WhatsApp"
          class="w-56 h-56 mx-auto rounded-xl border border-slate-200 object-contain"
        />

        <p class="text-xs text-slate-400 mt-4">
          O QR code atualiza automaticamente. Após escanear, esta janela fechará.
        </p>

        <button
          @click="fecharQrModal"
          class="mt-5 px-4 py-2 text-sm text-slate-600 hover:text-slate-800 transition-colors"
        >
          Fechar
        </button>
      </div>
    </div>
  </div>
</template>
