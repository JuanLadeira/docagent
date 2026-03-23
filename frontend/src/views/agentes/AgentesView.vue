<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api, type Agente, type McpServer } from '@/api/client'
import { useAgentsStore } from '@/stores/agents'

const router = useRouter()
const agentsStore = useAgentsStore()

const AVAILABLE_SKILLS = [
  { key: 'rag_search', label: 'Busca em Documentos', icon: '🔍' },
  { key: 'web_search', label: 'Busca na Web', icon: '🌐' },
]

const mcpServidores = ref<McpServer[]>([])

async function carregarMcpServidores() {
  try {
    const r = await api.listMcpServidores()
    mcpServidores.value = r.data.filter(s => s.tools.length > 0)
  } catch {
    // silencioso — MCP é opcional
  }
}

function labelMcpSkill(key: string) {
  const parts = key.split(':')
  if (parts.length !== 3) return key
  const [, sid, toolName] = parts
  const server = mcpServidores.value.find(s => String(s.id) === sid)
  return server ? `${server.nome} / ${toolName}` : toolName
}

const agentes = ref<Agente[]>([])
const loading = ref(false)
const error = ref('')
const deleting = ref<number | null>(null)

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

onMounted(() => {
  load()
  carregarMcpServidores()
})
</script>

<template>
  <div class="p-8 max-w-4xl">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-slate-800 text-2xl font-bold">Agentes</h1>
        <p class="text-slate-500 text-sm mt-1">Gerencie os agentes disponíveis para conversa</p>
      </div>
      <button
        @click="router.push('/agentes/novo')"
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
              <template v-if="skill.startsWith('mcp:')">
                🔌 {{ labelMcpSkill(skill) }}
              </template>
              <template v-else>
                {{ AVAILABLE_SKILLS.find(s => s.key === skill)?.icon }}
                {{ AVAILABLE_SKILLS.find(s => s.key === skill)?.label ?? skill }}
              </template>
            </span>
          </div>
          <p v-if="agente.system_prompt" class="text-slate-400 text-xs mt-2 italic truncate">
            Papel: {{ agente.system_prompt.slice(0, 80) }}{{ agente.system_prompt.length > 80 ? '...' : '' }}
          </p>
        </div>
        <div class="flex gap-2 flex-shrink-0">
          <button
            @click="router.push(`/agentes/${agente.id}/editar`)"
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

</template>
