<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api, type McpServer } from '@/api/client'

const servidores = ref<McpServer[]>([])
const carregando = ref(false)
const descobrindo = ref<number | null>(null)

const showModal = ref(false)
const editando = ref<McpServer | null>(null)
const salvando = ref(false)

const form = ref({
  nome: '',
  descricao: '',
  command: '',
  args: '',
  env: '',
  ativo: true,
})

async function carregar() {
  carregando.value = true
  try {
    const r = await api.listMcpServidores()
    servidores.value = r.data
  } finally {
    carregando.value = false
  }
}

function abrirCriar() {
  editando.value = null
  form.value = { nome: '', descricao: '', command: '', args: '', env: '', ativo: true }
  showModal.value = true
}

function abrirEditar(server: McpServer) {
  editando.value = server
  form.value = {
    nome: server.nome,
    descricao: server.descricao,
    command: server.command,
    args: server.args.join('\n'),
    env: Object.entries(server.env).map(([k, v]) => `${k}=${v}`).join('\n'),
    ativo: server.ativo,
  }
  showModal.value = true
}

function parseArgs(raw: string): string[] {
  return raw.split('\n').map(s => s.trim()).filter(Boolean)
}

function parseEnv(raw: string): Record<string, string> {
  const env: Record<string, string> = {}
  for (const line of raw.split('\n')) {
    const idx = line.indexOf('=')
    if (idx > 0) env[line.slice(0, idx).trim()] = line.slice(idx + 1).trim()
  }
  return env
}

async function salvar() {
  if (!form.value.nome.trim() || !form.value.command.trim() || salvando.value) return
  salvando.value = true
  try {
    const payload = {
      nome: form.value.nome.trim(),
      descricao: form.value.descricao.trim(),
      command: form.value.command.trim(),
      args: parseArgs(form.value.args),
      env: parseEnv(form.value.env),
      ativo: form.value.ativo,
    }
    if (editando.value) {
      await api.updateMcpServidor(editando.value.id, payload)
    } else {
      await api.createMcpServidor(payload)
    }
    showModal.value = false
    await carregar()
  } finally {
    salvando.value = false
  }
}

async function deletar(server: McpServer) {
  if (!confirm(`Remover servidor "${server.nome}"?`)) return
  await api.deleteMcpServidor(server.id)
  await carregar()
}

async function descobrir(server: McpServer) {
  descobrindo.value = server.id
  try {
    await api.descobrirTools(server.id)
    await carregar()
  } catch (e: unknown) {
    alert(`Erro ao descobrir tools: ${(e as { response?: { data?: { detail?: string }; message?: string } })?.response?.data?.detail ?? (e as Error).message}`)
  } finally {
    descobrindo.value = null
  }
}

const expandido = ref<Set<number>>(new Set())
function toggleExpand(id: number) {
  if (expandido.value.has(id)) expandido.value.delete(id)
  else expandido.value.add(id)
}

onMounted(carregar)
</script>

<template>
  <div class="p-6 max-w-4xl mx-auto h-full overflow-y-auto">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-xl font-semibold text-gray-800 dark:text-slate-100">Servidores MCP</h1>
        <p class="text-sm text-gray-500 dark:text-slate-400 mt-0.5">Registre servidores MCP para usar suas tools nos agentes</p>
      </div>
      <button
        class="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-500 transition-colors"
        @click="abrirCriar"
      >
        + Novo servidor
      </button>
    </div>

    <div v-if="carregando" class="text-center text-gray-400 dark:text-slate-500 py-12">Carregando...</div>

    <div v-else-if="servidores.length === 0" class="text-center text-gray-400 dark:text-slate-500 py-12">
      Nenhum servidor MCP registrado ainda.
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="server in servidores"
        :key="server.id"
        class="bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden"
      >
        <!-- Cabeçalho do servidor -->
        <div class="px-5 py-4 flex items-center gap-3">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="font-medium text-gray-800 dark:text-slate-100">{{ server.nome }}</span>
              <span
                class="text-xs px-1.5 py-0.5 rounded-full font-medium"
                :class="server.ativo ? 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400' : 'bg-gray-100 dark:bg-slate-700 text-gray-500 dark:text-slate-400'"
              >
                {{ server.ativo ? 'Ativo' : 'Inativo' }}
              </span>
            </div>
            <div class="text-xs text-gray-400 dark:text-slate-500 mt-0.5 font-mono">
              {{ server.command }} {{ server.args.join(' ') }}
            </div>
            <div v-if="server.descricao" class="text-xs text-gray-500 dark:text-slate-400 mt-0.5">{{ server.descricao }}</div>
          </div>

          <div class="flex items-center gap-2 flex-shrink-0">
            <button
              class="text-xs px-3 py-1.5 rounded-lg border border-gray-200 dark:border-slate-600 text-gray-600 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors disabled:opacity-50"
              :disabled="descobrindo === server.id"
              @click="descobrir(server)"
            >
              {{ descobrindo === server.id ? 'Descobrindo...' : 'Descobrir Tools' }}
            </button>
            <button
              v-if="server.tools.length > 0"
              class="text-xs px-2.5 py-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 transition-colors"
              @click="toggleExpand(server.id)"
            >
              {{ server.tools.length }} tool{{ server.tools.length !== 1 ? 's' : '' }}
              {{ expandido.has(server.id) ? '▲' : '▼' }}
            </button>
            <button
              class="text-xs px-2.5 py-1.5 rounded-lg text-gray-500 dark:text-slate-400 hover:text-gray-700 dark:hover:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700 transition-colors"
              @click="abrirEditar(server)"
            >
              Editar
            </button>
            <button
              class="text-xs px-2.5 py-1.5 rounded-lg text-red-500 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors"
              @click="deletar(server)"
            >
              Remover
            </button>
          </div>
        </div>

        <!-- Lista de tools (expansível) -->
        <div v-if="expandido.has(server.id) && server.tools.length > 0" class="border-t border-gray-100 dark:border-slate-700 px-5 py-3 bg-gray-50 dark:bg-slate-900/50">
          <div class="space-y-1.5">
            <div
              v-for="tool in server.tools"
              :key="tool.id"
              class="flex gap-2 text-xs"
            >
              <span class="font-mono font-medium text-indigo-700 dark:text-indigo-400 flex-shrink-0">{{ tool.tool_name }}</span>
              <span class="text-gray-500 dark:text-slate-400">{{ tool.description }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal criar/editar -->
    <div
      v-if="showModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      @click.self="showModal = false"
    >
      <div class="bg-white dark:bg-slate-800 rounded-xl shadow-xl w-full max-w-lg p-6">
        <h3 class="text-base font-semibold text-gray-800 dark:text-slate-100 mb-4">
          {{ editando ? 'Editar servidor' : 'Novo servidor MCP' }}
        </h3>

        <div class="space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-xs font-medium text-gray-600 dark:text-slate-300 mb-1">Nome *</label>
              <input
                v-model="form.nome"
                type="text"
                placeholder="Filesystem"
                class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div class="flex items-end gap-3">
              <label class="flex items-center gap-2 cursor-pointer pb-2">
                <input v-model="form.ativo" type="checkbox" class="rounded" />
                <span class="text-sm text-gray-700 dark:text-slate-200">Ativo</span>
              </label>
            </div>
          </div>

          <div>
            <label class="block text-xs font-medium text-gray-600 dark:text-slate-300 mb-1">Descrição</label>
            <input
              v-model="form.descricao"
              type="text"
              placeholder="Acesso a arquivos locais"
              class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label class="block text-xs font-medium text-gray-600 dark:text-slate-300 mb-1">Comando *</label>
            <input
              v-model="form.command"
              type="text"
              placeholder="npx"
              class="w-full px-3 py-2 text-sm font-mono border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label class="block text-xs font-medium text-gray-600 dark:text-slate-300 mb-1">
              Args <span class="text-gray-400 dark:text-slate-500">(um por linha)</span>
            </label>
            <textarea
              v-model="form.args"
              rows="3"
              placeholder="-y&#10;@modelcontextprotocol/server-filesystem&#10;/tmp"
              class="w-full px-3 py-2 text-sm font-mono border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            />
          </div>

          <div>
            <label class="block text-xs font-medium text-gray-600 dark:text-slate-300 mb-1">
              Variáveis de ambiente <span class="text-gray-400 dark:text-slate-500">(CHAVE=valor, uma por linha)</span>
            </label>
            <textarea
              v-model="form.env"
              rows="2"
              placeholder="GITHUB_TOKEN=ghp_xxx"
              class="w-full px-3 py-2 text-sm font-mono border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            />
          </div>
        </div>

        <div class="flex justify-end gap-2 mt-5">
          <button
            class="px-4 py-2 text-sm text-gray-600 dark:text-slate-300 hover:text-gray-800 dark:hover:text-white transition-colors"
            @click="showModal = false"
          >
            Cancelar
          </button>
          <button
            class="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-500 disabled:opacity-50 transition-colors"
            :disabled="salvando || !form.nome.trim() || !form.command.trim()"
            @click="salvar"
          >
            {{ salvando ? 'Salvando...' : editando ? 'Salvar alterações' : 'Registrar servidor' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
