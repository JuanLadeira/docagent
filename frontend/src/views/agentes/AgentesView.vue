<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api, type Agente, type AgenteCreate } from '@/api/client'
import { useAgentsStore } from '@/stores/agents'

const agentsStore = useAgentsStore()

const AVAILABLE_SKILLS = [
  { key: 'rag_search', label: 'Busca em Documentos', icon: '🔍', description: 'Busca semântica nos PDFs carregados' },
  { key: 'web_search', label: 'Busca na Web', icon: '🌐', description: 'Busca informações na internet via DuckDuckGo' },
]

const agentes = ref<Agente[]>([])
const loading = ref(false)
const error = ref('')

const showModal = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const deleting = ref<number | null>(null)

const form = ref<AgenteCreate>({
  nome: '',
  descricao: '',
  system_prompt: null,
  skill_names: [],
  ativo: true,
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.listAgentes()
    agentes.value = res.data
  } catch {
    error.value = 'Erro ao carregar agentes'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.value = { nome: '', descricao: '', system_prompt: null, skill_names: [], ativo: true }
  showModal.value = true
}

function openEdit(a: Agente) {
  editingId.value = a.id
  form.value = {
    nome: a.nome,
    descricao: a.descricao,
    system_prompt: a.system_prompt ?? null,
    skill_names: [...a.skill_names],
    ativo: a.ativo,
  }
  showModal.value = true
}

function toggleSkill(key: string) {
  const idx = form.value.skill_names.indexOf(key)
  if (idx === -1) form.value.skill_names.push(key)
  else form.value.skill_names.splice(idx, 1)
}

async function save() {
  if (!form.value.nome.trim()) return
  saving.value = true
  error.value = ''
  try {
    if (editingId.value !== null) {
      const res = await api.updateAgente(editingId.value, form.value)
      const idx = agentes.value.findIndex(a => a.id === editingId.value)
      if (idx !== -1) agentes.value[idx] = res.data
    } else {
      const res = await api.createAgente(form.value)
      agentes.value.push(res.data)
    }
    showModal.value = false
    agentsStore.invalidate()
  } catch {
    error.value = 'Erro ao salvar agente'
  } finally {
    saving.value = false
  }
}

async function remove(id: number) {
  if (!confirm('Remover este agente?')) return
  deleting.value = id
  try {
    await api.deleteAgente(id)
    agentes.value = agentes.value.filter(a => a.id !== id)
    agentsStore.invalidate()
  } catch {
    error.value = 'Erro ao remover agente'
  } finally {
    deleting.value = null
  }
}

onMounted(load)
</script>

<template>
  <div class="p-8 max-w-4xl">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-slate-800 text-2xl font-bold">Agentes</h1>
        <p class="text-slate-500 text-sm mt-1">Gerencie os agentes disponíveis para conversa</p>
      </div>
      <button
        @click="openCreate"
        class="bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
      >
        Novo agente
      </button>
    </div>

    <div v-if="error" class="bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-4 py-3 mb-4">
      {{ error }}
    </div>

    <div v-if="loading" class="text-slate-400 text-sm text-center py-12">Carregando...</div>

    <div v-else-if="agentes.length === 0" class="bg-white rounded-xl border border-slate-200 p-12 text-center">
      <div class="text-4xl mb-3">🤖</div>
      <h3 class="text-slate-700 font-semibold">Nenhum agente cadastrado</h3>
      <p class="text-slate-400 text-sm mt-2">Crie o primeiro agente para começar.</p>
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="agente in agentes"
        :key="agente.id"
        class="bg-white rounded-xl border border-slate-200 p-5 flex items-start gap-4"
      >
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <span class="text-slate-800 font-semibold">{{ agente.nome }}</span>
            <span
              class="px-2 py-0.5 rounded text-xs font-medium"
              :class="agente.ativo ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'"
            >
              {{ agente.ativo ? 'Ativo' : 'Inativo' }}
            </span>
          </div>
          <p class="text-slate-500 text-sm mb-2">{{ agente.descricao }}</p>
          <div class="flex flex-wrap gap-1.5">
            <span
              v-for="skill in agente.skill_names"
              :key="skill"
              class="px-2 py-0.5 bg-indigo-50 text-indigo-600 text-xs rounded font-medium"
            >
              {{ AVAILABLE_SKILLS.find(s => s.key === skill)?.icon }}
              {{ AVAILABLE_SKILLS.find(s => s.key === skill)?.label ?? skill }}
            </span>
          </div>
          <p v-if="agente.system_prompt" class="text-slate-400 text-xs mt-2 italic truncate">
            Papel: {{ agente.system_prompt.slice(0, 80) }}{{ agente.system_prompt.length > 80 ? '...' : '' }}
          </p>
        </div>
        <div class="flex gap-2 flex-shrink-0">
          <button
            @click="openEdit(agente)"
            class="px-3 py-1.5 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
          >
            Editar
          </button>
          <button
            @click="remove(agente.id)"
            :disabled="deleting === agente.id"
            class="px-3 py-1.5 text-sm text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50"
          >
            {{ deleting === agente.id ? '...' : 'Remover' }}
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Modal -->
  <Teleport to="body">
    <div
      v-if="showModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      @click.self="showModal = false"
    >
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-lg mx-4 p-6">
        <h2 class="text-slate-800 font-semibold text-lg mb-5">
          {{ editingId !== null ? 'Editar agente' : 'Novo agente' }}
        </h2>

        <div class="space-y-4">
          <div>
            <label class="block text-slate-500 text-sm mb-1">Nome</label>
            <input
              v-model="form.nome"
              type="text"
              placeholder="Ex: Analista Jurídico"
              class="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>

          <div>
            <label class="block text-slate-500 text-sm mb-1">Descrição</label>
            <input
              v-model="form.descricao"
              type="text"
              placeholder="Breve descrição do agente"
              class="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>

          <div>
            <label class="block text-slate-500 text-sm mb-2">Skills</label>
            <div class="space-y-2">
              <label
                v-for="skill in AVAILABLE_SKILLS"
                :key="skill.key"
                class="flex items-start gap-3 p-3 border rounded-lg cursor-pointer transition-colors"
                :class="form.skill_names.includes(skill.key)
                  ? 'border-indigo-400 bg-indigo-50'
                  : 'border-slate-200 hover:border-slate-300'"
              >
                <input
                  type="checkbox"
                  :checked="form.skill_names.includes(skill.key)"
                  @change="toggleSkill(skill.key)"
                  class="mt-0.5 accent-indigo-600"
                />
                <div>
                  <div class="text-sm font-medium text-slate-700">{{ skill.icon }} {{ skill.label }}</div>
                  <div class="text-xs text-slate-400">{{ skill.description }}</div>
                </div>
              </label>
            </div>
          </div>

          <div>
            <label class="block text-slate-500 text-sm mb-1">
              Papel (system prompt)
              <span class="text-slate-400 font-normal">— opcional</span>
            </label>
            <textarea
              v-model="form.system_prompt"
              rows="4"
              placeholder="Descreva o papel e comportamento do agente. Se vazio, usa o prompt padrão."
              class="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
            />
          </div>

          <div class="flex items-center gap-2">
            <input
              id="ativo"
              type="checkbox"
              v-model="form.ativo"
              class="accent-indigo-600"
            />
            <label for="ativo" class="text-sm text-slate-600">Agente ativo</label>
          </div>
        </div>

        <div v-if="error" class="mt-3 text-red-500 text-sm">{{ error }}</div>

        <div class="flex gap-3 mt-6">
          <button
            @click="showModal = false"
            class="flex-1 border border-slate-200 text-slate-600 text-sm font-medium py-2.5 rounded-lg hover:bg-slate-50 transition-colors"
          >
            Cancelar
          </button>
          <button
            @click="save"
            :disabled="saving || !form.nome.trim()"
            class="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium py-2.5 rounded-lg transition-colors"
          >
            {{ saving ? 'Salvando...' : 'Salvar' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
