<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { adminApi, type Plano } from '@/api/adminClient'

const planos = ref<Plano[]>([])
const loading = ref(true)

const showCreate = ref(false)
const createForm = ref({ nome: '', descricao: '', limite_agentes: 3, limite_documentos: 20, limite_sessoes: 10, ciclo_dias: 30, preco_mensal: '0.00', ativo: true })
const creating = ref(false)
const createError = ref('')

const editingPlano = ref<Plano | null>(null)
const editForm = ref({ nome: '', descricao: '', limite_agentes: 1, limite_documentos: 10, limite_sessoes: 5, ciclo_dias: 30, preco_mensal: '0.00', ativo: true })
const editSaving = ref(false)
const editError = ref('')

async function load() {
  loading.value = true
  try {
    const res = await adminApi.getPlanos()
    planos.value = res.data
  } finally {
    loading.value = false
  }
}

onMounted(load)

function openCreate() {
  createForm.value = { nome: '', descricao: '', limite_agentes: 3, limite_documentos: 20, limite_sessoes: 10, ciclo_dias: 30, preco_mensal: '0.00', ativo: true }
  createError.value = ''
  showCreate.value = true
}

async function submitCreate() {
  if (!createForm.value.nome.trim()) return
  creating.value = true
  createError.value = ''
  try {
    await adminApi.createPlano(createForm.value)
    showCreate.value = false
    await load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    createError.value = msg || 'Erro ao criar plano'
  } finally {
    creating.value = false
  }
}

function openEdit(plano: Plano) {
  editingPlano.value = plano
  editForm.value = { nome: plano.nome, descricao: plano.descricao, limite_agentes: plano.limite_agentes, limite_documentos: plano.limite_documentos, limite_sessoes: plano.limite_sessoes, ciclo_dias: plano.ciclo_dias, preco_mensal: plano.preco_mensal, ativo: plano.ativo }
  editError.value = ''
}

async function submitEdit() {
  if (!editingPlano.value) return
  editSaving.value = true
  editError.value = ''
  try {
    await adminApi.updatePlano(editingPlano.value.id, editForm.value)
    editingPlano.value = null
    await load()
  } catch {
    editError.value = 'Erro ao salvar'
  } finally {
    editSaving.value = false
  }
}

async function remove(id: number, nome: string) {
  if (!confirm(`Deletar o plano "${nome}"? Assinaturas vinculadas podem ser afetadas.`)) return
  try {
    await adminApi.deletePlano(id)
    await load()
  } catch {
    alert('Erro ao deletar plano')
  }
}

function formatMoeda(valor: string) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(valor))
}
</script>

<template>
  <div class="p-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-slate-800 dark:text-slate-100 text-2xl font-bold">Planos</h1>
        <p class="text-slate-500 dark:text-slate-400 text-sm mt-1">Planos SaaS disponíveis na plataforma</p>
      </div>
      <button @click="openCreate" class="bg-violet-600 hover:bg-violet-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
        + Novo Plano
      </button>
    </div>

    <!-- Modal: criar plano -->
    <div v-if="showCreate" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="showCreate = false">
      <div class="bg-white dark:bg-slate-800 rounded-2xl p-6 w-full max-w-md shadow-xl overflow-y-auto max-h-[90vh]">
        <h2 class="text-slate-800 dark:text-slate-100 font-semibold mb-4">Novo Plano</h2>
        <div class="space-y-3">
          <div>
            <label class="block text-slate-600 dark:text-slate-300 text-sm mb-1">Nome <span class="text-red-400">*</span></label>
            <input v-model="createForm.nome" placeholder="Ex: Starter, Pro, Enterprise"
              class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
          </div>
          <div>
            <label class="block text-slate-600 dark:text-slate-300 text-sm mb-1">Descrição</label>
            <input v-model="createForm.descricao" placeholder="Descrição breve do plano"
              class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
          </div>
          <div>
            <label class="block text-slate-600 dark:text-slate-300 text-sm mb-1">Preço Mensal (R$)</label>
            <input v-model="createForm.preco_mensal" type="number" min="0" step="0.01"
              class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
          </div>

          <!-- Legenda dos limites -->
          <div class="bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700 rounded-lg p-3 space-y-1.5">
            <p class="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">O que cada limite significa</p>
            <div class="flex gap-2 text-xs text-slate-500 dark:text-slate-400">
              <span class="font-medium text-slate-700 dark:text-slate-300 w-24 shrink-0">Agentes</span>
              <span>Bots de IA que o tenant pode criar. Cada agente tem seu próprio prompt, skills e base de conhecimento.</span>
            </div>
            <div class="flex gap-2 text-xs text-slate-500 dark:text-slate-400">
              <span class="font-medium text-slate-700 dark:text-slate-300 w-24 shrink-0">Documentos</span>
              <span>PDFs e arquivos enviados para a base RAG (total entre todos os agentes do tenant).</span>
            </div>
            <div class="flex gap-2 text-xs text-slate-500 dark:text-slate-400">
              <span class="font-medium text-slate-700 dark:text-slate-300 w-24 shrink-0">Sessões</span>
              <span>Conversas simultâneas abertas com os agentes. Cada usuário/atendimento gera uma sessão.</span>
            </div>
            <div class="flex gap-2 text-xs text-slate-500 dark:text-slate-400">
              <span class="font-medium text-slate-700 dark:text-slate-300 w-24 shrink-0">Ciclo (dias)</span>
              <span>Intervalo de renovação da assinatura. Ex: 30 = mensal, 365 = anual.</span>
            </div>
          </div>

          <p class="text-xs text-slate-400 dark:text-slate-500 uppercase font-semibold tracking-wide pt-1">Limites</p>
          <div class="grid grid-cols-3 gap-3">
            <div>
              <label class="block text-slate-600 dark:text-slate-300 text-xs mb-1">Agentes</label>
              <input v-model.number="createForm.limite_agentes" type="number" min="1"
                class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
            </div>
            <div>
              <label class="block text-slate-600 dark:text-slate-300 text-xs mb-1">Documentos</label>
              <input v-model.number="createForm.limite_documentos" type="number" min="1"
                class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
            </div>
            <div>
              <label class="block text-slate-600 dark:text-slate-300 text-xs mb-1">Sessões</label>
              <input v-model.number="createForm.limite_sessoes" type="number" min="1"
                class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
            </div>
          </div>
          <div>
            <label class="block text-slate-600 dark:text-slate-300 text-sm mb-1">Ciclo (dias)</label>
            <input v-model.number="createForm.ciclo_dias" type="number" min="1"
              class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
          </div>
          <div class="flex items-center gap-2">
            <input id="ativo-create" v-model="createForm.ativo" type="checkbox" class="accent-violet-600" />
            <label for="ativo-create" class="text-slate-600 dark:text-slate-300 text-sm">Plano ativo</label>
          </div>
          <div v-if="createError" class="text-red-500 text-sm">{{ createError }}</div>
        </div>
        <div class="flex gap-3 mt-5">
          <button @click="submitCreate" :disabled="creating || !createForm.nome.trim()"
            class="flex-1 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg py-2 text-sm font-medium transition-colors">
            {{ creating ? 'Criando...' : 'Criar' }}
          </button>
          <button @click="showCreate = false"
            class="flex-1 border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 rounded-lg py-2 text-sm transition-colors">
            Cancelar
          </button>
        </div>
      </div>
    </div>

    <!-- Modal: editar plano -->
    <div v-if="editingPlano" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="editingPlano = null">
      <div class="bg-white dark:bg-slate-800 rounded-2xl p-6 w-full max-w-md shadow-xl overflow-y-auto max-h-[90vh]">
        <h2 class="text-slate-800 dark:text-slate-100 font-semibold mb-4">Editar Plano</h2>
        <div class="space-y-3">
          <div>
            <label class="block text-slate-600 dark:text-slate-300 text-sm mb-1">Nome</label>
            <input v-model="editForm.nome"
              class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
          </div>
          <div>
            <label class="block text-slate-600 dark:text-slate-300 text-sm mb-1">Descrição</label>
            <input v-model="editForm.descricao"
              class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
          </div>
          <div>
            <label class="block text-slate-600 dark:text-slate-300 text-sm mb-1">Preço Mensal (R$)</label>
            <input v-model="editForm.preco_mensal" type="number" min="0" step="0.01"
              class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
          </div>

          <p class="text-xs text-slate-400 dark:text-slate-500 uppercase font-semibold tracking-wide pt-1">Limites</p>
          <div class="bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700 rounded-lg p-3 space-y-1.5">
            <div class="flex gap-2 text-xs text-slate-500 dark:text-slate-400">
              <span class="font-medium text-slate-700 dark:text-slate-300 w-24 shrink-0">Agentes</span>
              <span>Bots de IA que o tenant pode criar. Cada agente tem seu próprio prompt, skills e base de conhecimento.</span>
            </div>
            <div class="flex gap-2 text-xs text-slate-500 dark:text-slate-400">
              <span class="font-medium text-slate-700 dark:text-slate-300 w-24 shrink-0">Documentos</span>
              <span>PDFs e arquivos enviados para a base RAG (total entre todos os agentes do tenant).</span>
            </div>
            <div class="flex gap-2 text-xs text-slate-500 dark:text-slate-400">
              <span class="font-medium text-slate-700 dark:text-slate-300 w-24 shrink-0">Sessões</span>
              <span>Conversas simultâneas abertas com os agentes. Cada usuário/atendimento gera uma sessão.</span>
            </div>
            <div class="flex gap-2 text-xs text-slate-500 dark:text-slate-400">
              <span class="font-medium text-slate-700 dark:text-slate-300 w-24 shrink-0">Ciclo (dias)</span>
              <span>Intervalo de renovação da assinatura. Ex: 30 = mensal, 365 = anual.</span>
            </div>
          </div>
          <div class="grid grid-cols-3 gap-3">
            <div>
              <label class="block text-slate-600 dark:text-slate-300 text-xs mb-1">Agentes</label>
              <input v-model.number="editForm.limite_agentes" type="number" min="1"
                class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
            </div>
            <div>
              <label class="block text-slate-600 dark:text-slate-300 text-xs mb-1">Documentos</label>
              <input v-model.number="editForm.limite_documentos" type="number" min="1"
                class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
            </div>
            <div>
              <label class="block text-slate-600 dark:text-slate-300 text-xs mb-1">Sessões</label>
              <input v-model.number="editForm.limite_sessoes" type="number" min="1"
                class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
            </div>
          </div>
          <div>
            <label class="block text-slate-600 dark:text-slate-300 text-sm mb-1">Ciclo (dias)</label>
            <input v-model.number="editForm.ciclo_dias" type="number" min="1"
              class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
          </div>
          <div class="flex items-center gap-2">
            <input id="ativo-edit" v-model="editForm.ativo" type="checkbox" class="accent-violet-600" />
            <label for="ativo-edit" class="text-slate-600 dark:text-slate-300 text-sm">Plano ativo</label>
          </div>
          <div v-if="editError" class="text-red-500 text-sm">{{ editError }}</div>
        </div>
        <div class="flex gap-3 mt-5">
          <button @click="submitEdit" :disabled="editSaving"
            class="flex-1 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg py-2 text-sm font-medium transition-colors">
            {{ editSaving ? 'Salvando...' : 'Salvar' }}
          </button>
          <button @click="editingPlano = null"
            class="flex-1 border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 rounded-lg py-2 text-sm transition-colors">
            Cancelar
          </button>
        </div>
      </div>
    </div>

    <!-- Tabela -->
    <div class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-slate-400 text-sm">Carregando...</div>
      <div v-else-if="planos.length === 0" class="p-8 text-center text-slate-400 text-sm">
        Nenhum plano cadastrado
      </div>
      <table v-else class="w-full text-sm">
        <thead class="bg-slate-50 dark:bg-slate-700/50 border-b border-slate-200 dark:border-slate-700">
          <tr>
            <th class="text-left px-4 py-3 text-slate-500 dark:text-slate-400 font-medium">#</th>
            <th class="text-left px-4 py-3 text-slate-500 dark:text-slate-400 font-medium">Nome</th>
            <th class="text-left px-4 py-3 text-slate-500 dark:text-slate-400 font-medium">Preço</th>
            <th class="text-left px-4 py-3 text-slate-500 dark:text-slate-400 font-medium">Agentes</th>
            <th class="text-left px-4 py-3 text-slate-500 dark:text-slate-400 font-medium">Docs</th>
            <th class="text-left px-4 py-3 text-slate-500 dark:text-slate-400 font-medium">Ciclo</th>
            <th class="text-left px-4 py-3 text-slate-500 dark:text-slate-400 font-medium">Status</th>
            <th class="px-4 py-3" />
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100 dark:divide-slate-700">
          <tr v-for="plano in planos" :key="plano.id" class="hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
            <td class="px-4 py-3 text-slate-400 dark:text-slate-500">{{ plano.id }}</td>
            <td class="px-4 py-3">
              <div class="font-medium text-slate-800 dark:text-slate-200">{{ plano.nome }}</div>
              <div v-if="plano.descricao" class="text-xs text-slate-400 dark:text-slate-500 mt-0.5">{{ plano.descricao }}</div>
            </td>
            <td class="px-4 py-3 text-slate-700 dark:text-slate-300 font-medium">{{ formatMoeda(plano.preco_mensal) }}</td>
            <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ plano.limite_agentes }}</td>
            <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ plano.limite_documentos }}</td>
            <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ plano.ciclo_dias }}d</td>
            <td class="px-4 py-3">
              <span class="text-xs px-2 py-0.5 rounded-full font-medium"
                :class="plano.ativo ? 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400' : 'bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400'">
                {{ plano.ativo ? 'Ativo' : 'Inativo' }}
              </span>
            </td>
            <td class="px-4 py-3">
              <div class="flex gap-3 justify-end">
                <button @click="openEdit(plano)" class="text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 text-xs font-medium">Editar</button>
                <button @click="remove(plano.id, plano.nome)" class="text-red-500 hover:text-red-400 text-xs font-medium">Deletar</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
