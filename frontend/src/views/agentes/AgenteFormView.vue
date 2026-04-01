<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type AgenteCreate, type McpServer, type Documento } from '@/api/client'
import { useAgentsStore } from '@/stores/agents'

const route = useRoute()
const router = useRouter()
const agentsStore = useAgentsStore()

const isEditing = computed(() => !!route.params.id)
const agenteId = computed(() => isEditing.value ? Number(route.params.id) : null)

const AVAILABLE_SKILLS = [
  { key: 'rag_search', label: 'Busca em Documentos', icon: '🔍', description: 'Busca semântica nos PDFs carregados' },
  { key: 'web_search', label: 'Busca na Web', icon: '🌐', description: 'Busca informações na internet via DuckDuckGo' },
  { key: 'human_handoff', label: 'Transferência Humana', icon: '🙋', description: 'Detecta quando o usuário quer falar com um atendente e sinaliza para os operadores' },
]

const form = ref<AgenteCreate>({
  nome: '',
  descricao: '',
  system_prompt: null,
  skill_names: [],
  ativo: true,
})

const mcpServidores = ref<McpServer[]>([])
const documentos = ref<Documento[]>([])
const loading = ref(false)
const saving = ref(false)
const uploadingDoc = ref(false)
const docError = ref('')
const error = ref('')

function mcpSkillKey(serverId: number, toolName: string) {
  return `mcp:${serverId}:${toolName}`
}

function toggleSkill(key: string) {
  const idx = form.value.skill_names.indexOf(key)
  if (idx === -1) form.value.skill_names.push(key)
  else form.value.skill_names.splice(idx, 1)
}

function serverAllSelected(server: McpServer): boolean {
  return server.tools.every(t => form.value.skill_names.includes(mcpSkillKey(server.id, t.tool_name)))
}

function toggleServerAll(server: McpServer) {
  if (serverAllSelected(server)) {
    const keys = new Set(server.tools.map(t => mcpSkillKey(server.id, t.tool_name)))
    form.value.skill_names = form.value.skill_names.filter(k => !keys.has(k))
  } else {
    for (const tool of server.tools) {
      const key = mcpSkillKey(server.id, tool.tool_name)
      if (!form.value.skill_names.includes(key)) form.value.skill_names.push(key)
    }
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [mcpRes] = await Promise.all([
      api.listMcpServidores(),
      isEditing.value ? loadAgente() : Promise.resolve(),
    ])
    mcpServidores.value = mcpRes.data.filter(s => s.ativo && s.tools.length > 0)
    if (isEditing.value) await loadDocumentos()
  } catch {
    error.value = 'Erro ao carregar dados'
  } finally {
    loading.value = false
  }
}

async function loadDocumentos() {
  const res = await api.listDocumentos(agenteId.value!)
  documentos.value = res.data
}

async function handleUploadDoc(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  docError.value = ''
  uploadingDoc.value = true
  try {
    const res = await api.uploadDocumento(agenteId.value!, file)
    documentos.value.push(res.data)
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status
    if (status === 409) {
      docError.value = 'Este arquivo já foi indexado para este agente.'
    } else {
      docError.value = 'Erro ao indexar documento.'
    }
  } finally {
    uploadingDoc.value = false
    ;(event.target as HTMLInputElement).value = ''
  }
}

async function removerDocumento(docId: number) {
  docError.value = ''
  try {
    await api.removerDocumento(agenteId.value!, docId)
    documentos.value = documentos.value.filter(d => d.id !== docId)
  } catch {
    docError.value = 'Erro ao remover documento.'
  }
}

async function loadAgente() {
  const res = await api.getAgente(agenteId.value!)
  const a = res.data
  form.value = {
    nome: a.nome,
    descricao: a.descricao,
    system_prompt: a.system_prompt ?? null,
    skill_names: [...a.skill_names],
    ativo: a.ativo,
  }
}

async function save() {
  if (!form.value.nome.trim()) return
  saving.value = true
  error.value = ''
  try {
    if (isEditing.value) {
      await api.updateAgente(agenteId.value!, form.value)
    } else {
      await api.createAgente(form.value)
    }
    agentsStore.invalidate()
    router.push('/agentes')
  } catch {
    error.value = 'Erro ao salvar agente'
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="h-full overflow-y-auto bg-slate-50 dark:bg-slate-900">
    <!-- Header -->
    <div class="sticky top-0 z-10 bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-8 py-4 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <button
          @click="router.push('/agentes')"
          class="text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
        >
          ←
        </button>
        <div class="text-slate-300 dark:text-slate-600">/</div>
        <span class="text-slate-500 dark:text-slate-400 text-sm hover:text-slate-700 dark:hover:text-slate-200 cursor-pointer" @click="router.push('/agentes')">Agentes</span>
        <div class="text-slate-300 dark:text-slate-600">/</div>
        <span class="text-slate-800 dark:text-slate-100 text-sm font-medium">
          {{ isEditing ? (form.nome || 'Editar agente') : 'Novo agente' }}
        </span>
      </div>

      <div class="flex items-center gap-3">
        <div v-if="error" class="text-red-500 dark:text-red-400 text-sm">{{ error }}</div>
        <button
          @click="router.push('/agentes')"
          class="px-4 py-2 text-sm text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
        >
          Cancelar
        </button>
        <button
          @click="save"
          :disabled="saving || !form.nome.trim()"
          class="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 rounded-lg transition-colors"
        >
          {{ saving ? 'Salvando...' : 'Salvar agente' }}
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-24 text-slate-400 dark:text-slate-500 text-sm">
      Carregando...
    </div>

    <!-- Form -->
    <div v-else class="max-w-6xl mx-auto px-8 py-8 grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">

      <!-- Coluna esquerda: informações básicas -->
      <div class="space-y-6">
        <div class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6 space-y-5">
          <h2 class="text-slate-700 dark:text-slate-200 font-semibold text-sm uppercase tracking-wide">Informações</h2>

          <div>
            <label class="block text-slate-600 dark:text-slate-300 text-sm font-medium mb-1.5">Nome <span class="text-red-400">*</span></label>
            <input
              v-model="form.nome"
              type="text"
              placeholder="Ex: Analista Jurídico"
              class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2.5 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>

          <div>
            <label class="block text-slate-600 dark:text-slate-300 text-sm font-medium mb-1.5">Descrição</label>
            <input
              v-model="form.descricao"
              type="text"
              placeholder="Breve descrição do que este agente faz"
              class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2.5 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>

          <div>
            <label class="block text-slate-600 dark:text-slate-300 text-sm font-medium mb-1.5">
              Papel (system prompt)
              <span class="text-slate-400 dark:text-slate-500 font-normal ml-1">— opcional</span>
            </label>
            <textarea
              v-model="form.system_prompt"
              rows="8"
              placeholder="Descreva o papel e comportamento do agente. Se vazio, usa o prompt padrão do sistema."
              class="w-full border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2.5 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
            />
            <p class="text-xs text-slate-400 dark:text-slate-500 mt-1">
              Dica: seja específico sobre o tom, formato de resposta e limitações do agente.
            </p>
          </div>

          <div class="flex items-center gap-2 pt-1">
            <input
              id="ativo"
              type="checkbox"
              v-model="form.ativo"
              class="accent-indigo-600 w-4 h-4"
            />
            <label for="ativo" class="text-sm text-slate-600 dark:text-slate-300">Agente ativo</label>
          </div>
        </div>

        <!-- Card Documentos — apenas no modo edição -->
        <div v-if="isEditing" class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
          <h2 class="text-slate-700 dark:text-slate-200 font-semibold text-sm uppercase tracking-wide mb-4">
            Documentos
            <span class="ml-2 text-xs font-normal text-slate-400 dark:text-slate-500 normal-case">
              {{ documentos.length }} indexado{{ documentos.length !== 1 ? 's' : '' }}
            </span>
          </h2>

          <div class="space-y-2 mb-4">
            <div
              v-for="doc in documentos"
              :key="doc.id"
              class="flex items-center justify-between p-3 border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900/50"
            >
              <div class="min-w-0 mr-3">
                <div class="text-sm font-medium text-slate-700 dark:text-slate-200 truncate">{{ doc.filename }}</div>
                <div class="text-xs text-slate-400 dark:text-slate-500">{{ doc.chunks }} chunks</div>
              </div>
              <button
                @click="removerDocumento(doc.id)"
                class="text-xs text-red-400 hover:text-red-600 dark:hover:text-red-300 transition-colors shrink-0"
              >
                Remover
              </button>
            </div>
            <div v-if="documentos.length === 0" class="text-sm text-slate-400 dark:text-slate-500 py-1">
              Nenhum documento indexado para este agente.
            </div>
          </div>

          <div v-if="docError" class="text-xs text-red-500 dark:text-red-400 mb-3">{{ docError }}</div>

          <div>
            <span class="text-xs text-slate-500 dark:text-slate-400 font-medium mb-1 block">Adicionar PDF</span>
            <input
              type="file"
              accept=".pdf"
              @change="handleUploadDoc"
              :disabled="uploadingDoc"
              class="block w-full text-sm text-slate-500 dark:text-slate-400
                     file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0
                     file:text-xs file:font-medium file:bg-indigo-50 dark:file:bg-indigo-900/30 file:text-indigo-700 dark:file:text-indigo-400
                     hover:file:bg-indigo-100 dark:hover:file:bg-indigo-900/50 disabled:opacity-50"
            />
            <span v-if="uploadingDoc" class="text-xs text-slate-400 dark:text-slate-500 mt-1 block">Indexando...</span>
          </div>
        </div>
      </div>

      <!-- Coluna direita: skills -->
      <div class="space-y-4 lg:sticky lg:top-24">
        <div class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
          <h2 class="text-slate-700 dark:text-slate-200 font-semibold text-sm uppercase tracking-wide mb-4">
            Skills
            <span class="ml-2 text-xs font-normal text-slate-400 dark:text-slate-500 normal-case">
              {{ form.skill_names.length }} selecionada{{ form.skill_names.length !== 1 ? 's' : '' }}
            </span>
          </h2>

          <div class="space-y-3 max-h-[60vh] overflow-y-auto pr-1">

            <!-- Skills nativas -->
            <div class="text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wide pb-1">Nativas</div>
            <label
              v-for="skill in AVAILABLE_SKILLS"
              :key="skill.key"
              class="flex items-start gap-3 p-3 border rounded-lg cursor-pointer transition-colors"
              :class="form.skill_names.includes(skill.key)
                ? 'border-indigo-400 dark:border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20'
                : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700/50'"
            >
              <input
                type="checkbox"
                :checked="form.skill_names.includes(skill.key)"
                @change="toggleSkill(skill.key)"
                class="mt-0.5 accent-indigo-600"
              />
              <div>
                <div class="text-sm font-medium text-slate-700 dark:text-slate-200">{{ skill.icon }} {{ skill.label }}</div>
                <div class="text-xs text-slate-400 dark:text-slate-500 mt-0.5">{{ skill.description }}</div>
              </div>
            </label>

            <!-- Skills MCP por servidor -->
            <template v-if="mcpServidores.length > 0">
              <template v-for="server in mcpServidores" :key="`mcp-${server.id}`">
                <div class="text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wide pt-2 pb-1 flex items-center justify-between">
                  <span>🔌 MCP: {{ server.nome }}</span>
                  <button
                    type="button"
                    @click="toggleServerAll(server)"
                    class="font-normal normal-case text-indigo-500 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors"
                  >
                    {{ serverAllSelected(server) ? 'Desmarcar todas' : 'Selecionar todas' }}
                  </button>
                </div>
                <label
                  v-for="tool in server.tools"
                  :key="mcpSkillKey(server.id, tool.tool_name)"
                  class="flex items-start gap-3 p-3 border rounded-lg cursor-pointer transition-colors"
                  :class="form.skill_names.includes(mcpSkillKey(server.id, tool.tool_name))
                    ? 'border-indigo-400 dark:border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20'
                    : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700/50'"
                >
                  <input
                    type="checkbox"
                    :checked="form.skill_names.includes(mcpSkillKey(server.id, tool.tool_name))"
                    @change="toggleSkill(mcpSkillKey(server.id, tool.tool_name))"
                    class="mt-0.5 accent-indigo-600"
                  />
                  <div class="min-w-0">
                    <div class="text-sm font-medium text-slate-700 dark:text-slate-200 font-mono">{{ tool.tool_name }}</div>
                    <div class="text-xs text-slate-400 dark:text-slate-500 mt-0.5 leading-relaxed">{{ tool.description }}</div>
                  </div>
                </label>
              </template>
            </template>

            <div v-else class="text-xs text-slate-400 dark:text-slate-500 py-2">
              Nenhum servidor MCP com tools descobertas. Acesse
              <RouterLink to="/servidores-mcp" class="text-indigo-500 dark:text-indigo-400 underline">Servidores MCP</RouterLink>
              para configurar.
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
