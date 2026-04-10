<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { adminApi, type Tenant } from '@/api/adminClient'

interface TenantUser {
  id: number
  username: string
  email: string
  nome: string
  ativo: boolean
  role: string
}

const tenants = ref<Tenant[]>([])
const loading = ref(true)

// ── Criar tenant ──────────────────────────────────────────────────────────────
const showCreateForm = ref(false)
const createForm = ref({
  nome: '',
  descricao: '',
  owner_username: '',
  owner_email: '',
  owner_nome: '',
  owner_password: '',
})
const creating = ref(false)
const createError = ref('')

// ── Editar tenant ─────────────────────────────────────────────────────────────
const editingTenant = ref<Tenant | null>(null)
const editForm = ref({ nome: '', descricao: '', llm_provider: '' as string | null, llm_model: '' as string | null, llm_api_key: '' as string | null })
const editSaving = ref(false)
const editError = ref('')

// ── Usuários do tenant ────────────────────────────────────────────────────────
const usuariosTenant = ref<Tenant | null>(null)
const usuarios = ref<TenantUser[]>([])
const usuariosLoading = ref(false)
const showAddUser = ref(false)
const addUserForm = ref({ username: '', email: '', nome: '', password: '', role: 'MEMBER' })
const addUserSaving = ref(false)
const addUserError = ref('')

async function load() {
  loading.value = true
  try {
    const res = await adminApi.getTenants()
    tenants.value = res.data
  } finally {
    loading.value = false
  }
}

onMounted(load)

function openCreate() {
  createForm.value = { nome: '', descricao: '', owner_username: '', owner_email: '', owner_nome: '', owner_password: '' }
  createError.value = ''
  showCreateForm.value = true
}

async function submitCreate() {
  if (!createForm.value.nome.trim() || !createForm.value.owner_username.trim() || !createForm.value.owner_password.trim()) return
  creating.value = true
  createError.value = ''
  try {
    const tenantRes = await adminApi.createTenant({ nome: createForm.value.nome, descricao: createForm.value.descricao || undefined })
    const tenant = tenantRes.data
    await adminApi.createTenantUsuario(tenant.id, {
      username: createForm.value.owner_username,
      email: createForm.value.owner_email || `${createForm.value.owner_username}@${createForm.value.nome.toLowerCase().replace(/\s+/g, '')}.com`,
      nome: createForm.value.owner_nome || createForm.value.owner_username,
      password: createForm.value.owner_password,
      role: 'OWNER',
    })
    showCreateForm.value = false
    await load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    createError.value = msg || 'Erro ao criar tenant'
  } finally {
    creating.value = false
  }
}

function openEdit(tenant: Tenant) {
  editingTenant.value = tenant
  editForm.value = { nome: tenant.nome, descricao: tenant.descricao ?? '', llm_provider: tenant.llm_provider ?? '', llm_model: tenant.llm_model ?? '', llm_api_key: '' }
  editError.value = ''
}

async function submitEdit() {
  if (!editingTenant.value) return
  editSaving.value = true
  editError.value = ''
  try {
    const payload: Parameters<typeof adminApi.updateTenant>[1] = {
      nome: editForm.value.nome,
      descricao: editForm.value.descricao || undefined,
      llm_provider: editForm.value.llm_provider || null,
      llm_model: editForm.value.llm_model || null,
    }
    if (editForm.value.llm_api_key) payload.llm_api_key = editForm.value.llm_api_key
    await adminApi.updateTenant(editingTenant.value.id, payload)
    editingTenant.value = null
    await load()
  } catch {
    editError.value = 'Erro ao salvar'
  } finally {
    editSaving.value = false
  }
}

async function remove(id: number) {
  if (!confirm('Deletar este tenant e todos seus dados?')) return
  try {
    await adminApi.deleteTenant(id)
    await load()
  } catch {
    alert('Erro ao deletar')
  }
}

async function openUsuarios(tenant: Tenant) {
  usuariosTenant.value = tenant
  showAddUser.value = false
  addUserError.value = ''
  usuariosLoading.value = true
  try {
    const res = await adminApi.getTenantUsuarios(tenant.id)
    usuarios.value = res.data
  } finally {
    usuariosLoading.value = false
  }
}

async function submitAddUser() {
  if (!usuariosTenant.value || !addUserForm.value.username.trim() || !addUserForm.value.password.trim()) return
  addUserSaving.value = true
  addUserError.value = ''
  try {
    const res = await adminApi.createTenantUsuario(usuariosTenant.value.id, {
      username: addUserForm.value.username,
      email: addUserForm.value.email || `${addUserForm.value.username}@docagent.com`,
      nome: addUserForm.value.nome || addUserForm.value.username,
      password: addUserForm.value.password,
      role: addUserForm.value.role,
    })
    usuarios.value.push(res.data as TenantUser)
    showAddUser.value = false
    addUserForm.value = { username: '', email: '', nome: '', password: '', role: 'MEMBER' }
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    addUserError.value = msg || 'Erro ao criar usuário'
  } finally {
    addUserSaving.value = false
  }
}

async function removeUsuario(id: number) {
  if (!confirm('Remover este usuário?')) return
  try {
    await adminApi.deleteUsuario(id)
    usuarios.value = usuarios.value.filter(u => u.id !== id)
  } catch {
    alert('Erro ao remover usuário')
  }
}
</script>

<template>
  <div class="p-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-slate-800 dark:text-slate-100 text-2xl font-bold">Tenants</h1>
        <p class="text-slate-500 dark:text-slate-400 text-sm mt-1">Organizações cadastradas na plataforma</p>
      </div>
      <button
        @click="openCreate"
        class="bg-violet-600 hover:bg-violet-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
      >
        + Novo Tenant
      </button>
    </div>

    <!-- Modal: criar tenant -->
    <div
      v-if="showCreateForm"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="showCreateForm = false"
    >
      <div class="bg-white dark:bg-slate-800 rounded-2xl p-6 w-full max-w-md shadow-xl overflow-y-auto max-h-[90vh]">
        <h2 class="text-slate-800 dark:text-slate-100 font-semibold mb-4">Novo Tenant</h2>
        <div class="space-y-3">
          <p class="text-xs text-slate-400 dark:text-slate-500 uppercase font-semibold tracking-wide">Tenant</p>
          <div>
            <label class="block text-slate-600 dark:text-slate-300 text-sm mb-1">Nome <span class="text-red-400">*</span></label>
            <input v-model="createForm.nome" placeholder="Ex: Escritório Silva & Associados"
              class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
          </div>
          <div>
            <label class="block text-slate-600 dark:text-slate-300 text-sm mb-1">Descrição</label>
            <input v-model="createForm.descricao"
              class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
          </div>

          <p class="text-xs text-slate-400 dark:text-slate-500 uppercase font-semibold tracking-wide pt-2">Usuário owner</p>
          <div>
            <label class="block text-slate-600 dark:text-slate-300 text-sm mb-1">Username <span class="text-red-400">*</span></label>
            <input v-model="createForm.owner_username" placeholder="Ex: joao.silva"
              class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
          </div>
          <div>
            <label class="block text-slate-600 dark:text-slate-300 text-sm mb-1">Nome completo</label>
            <input v-model="createForm.owner_nome" placeholder="Ex: João Silva"
              class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
          </div>
          <div>
            <label class="block text-slate-600 dark:text-slate-300 text-sm mb-1">E-mail</label>
            <input v-model="createForm.owner_email" type="email" placeholder="Ex: joao@empresa.com"
              class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
          </div>
          <div>
            <label class="block text-slate-600 dark:text-slate-300 text-sm mb-1">Senha <span class="text-red-400">*</span></label>
            <input v-model="createForm.owner_password" type="password"
              class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
          </div>
          <div v-if="createError" class="text-red-500 text-sm">{{ createError }}</div>
        </div>
        <div class="flex gap-3 mt-5">
          <button @click="submitCreate"
            :disabled="creating || !createForm.nome.trim() || !createForm.owner_username.trim() || !createForm.owner_password.trim()"
            class="flex-1 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg py-2 text-sm font-medium transition-colors">
            {{ creating ? 'Criando...' : 'Criar' }}
          </button>
          <button @click="showCreateForm = false"
            class="flex-1 border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 rounded-lg py-2 text-sm transition-colors">
            Cancelar
          </button>
        </div>
      </div>
    </div>

    <!-- Modal: editar tenant -->
    <div
      v-if="editingTenant"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="editingTenant = null"
    >
      <div class="bg-white dark:bg-slate-800 rounded-2xl p-6 w-full max-w-md shadow-xl overflow-y-auto max-h-[90vh]">
        <h2 class="text-slate-800 dark:text-slate-100 font-semibold mb-4">Editar Tenant</h2>
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

          <p class="text-xs text-slate-400 dark:text-slate-500 uppercase font-semibold tracking-wide pt-2">Configuração LLM</p>
          <div>
            <label class="block text-slate-600 dark:text-slate-300 text-sm mb-1">Provider</label>
            <select v-model="editForm.llm_provider"
              class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500">
              <option value="">Padrão do sistema (Ollama)</option>
              <option value="openai">OpenAI</option>
              <option value="groq">Groq</option>
              <option value="anthropic">Anthropic (Claude)</option>
              <option value="gemini">Google Gemini</option>
              <option value="ollama">Ollama (local)</option>
            </select>
          </div>
          <div v-if="editForm.llm_provider && editForm.llm_provider !== 'ollama'">
            <label class="block text-slate-600 dark:text-slate-300 text-sm mb-1">Modelo</label>
            <input v-model="editForm.llm_model" placeholder="Ex: gpt-4o-mini, claude-3-haiku-20240307"
              class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
          </div>
          <div v-if="editForm.llm_provider && editForm.llm_provider !== 'ollama'">
            <label class="block text-slate-600 dark:text-slate-300 text-sm mb-1">
              API Key
              <span v-if="editingTenant?.llm_api_key_set" class="ml-1 text-xs text-green-500">(configurada)</span>
              <span v-else class="ml-1 text-xs text-slate-400">(não configurada)</span>
            </label>
            <input v-model="editForm.llm_api_key" type="password" placeholder="Deixe em branco para não alterar"
              class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
          </div>
          <div v-if="editError" class="text-red-500 text-sm">{{ editError }}</div>
        </div>
        <div class="flex gap-3 mt-5">
          <button @click="submitEdit" :disabled="editSaving"
            class="flex-1 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg py-2 text-sm font-medium transition-colors">
            {{ editSaving ? 'Salvando...' : 'Salvar' }}
          </button>
          <button @click="editingTenant = null"
            class="flex-1 border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 rounded-lg py-2 text-sm transition-colors">
            Cancelar
          </button>
        </div>
      </div>
    </div>

    <!-- Modal: usuários do tenant -->
    <div
      v-if="usuariosTenant"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="usuariosTenant = null"
    >
      <div class="bg-white dark:bg-slate-800 rounded-2xl p-6 w-full max-w-lg shadow-xl max-h-[90vh] flex flex-col">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-slate-800 dark:text-slate-100 font-semibold">Usuários — {{ usuariosTenant.nome }}</h2>
          <button @click="usuariosTenant = null" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-xl leading-none">&times;</button>
        </div>

        <div class="flex-1 overflow-y-auto space-y-2 mb-4">
          <div v-if="usuariosLoading" class="text-slate-400 text-sm text-center py-4">Carregando...</div>
          <div
            v-for="u in usuarios" :key="u.id"
            class="flex items-center justify-between px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg text-sm"
          >
            <div>
              <span class="font-medium text-slate-800 dark:text-slate-200">{{ u.username }}</span>
              <span class="ml-2 text-slate-400 dark:text-slate-500">{{ u.nome }}</span>
              <span
                class="ml-2 text-xs px-1.5 py-0.5 rounded font-medium"
                :class="u.role === 'OWNER' ? 'bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-400' : 'bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400'"
              >{{ u.role }}</span>
            </div>
            <button @click="removeUsuario(u.id)" class="text-red-400 hover:text-red-600 text-xs">Remover</button>
          </div>
          <div v-if="!usuariosLoading && usuarios.length === 0" class="text-slate-400 text-sm text-center py-4">
            Nenhum usuário neste tenant.
          </div>
        </div>

        <div v-if="showAddUser" class="border-t border-slate-200 dark:border-slate-700 pt-4 space-y-3">
          <p class="text-xs text-slate-500 dark:text-slate-400 font-semibold uppercase tracking-wide">Novo usuário</p>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-slate-600 dark:text-slate-300 text-xs mb-1">Username *</label>
              <input v-model="addUserForm.username"
                class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded px-2 py-1.5 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
            </div>
            <div>
              <label class="block text-slate-600 dark:text-slate-300 text-xs mb-1">Senha *</label>
              <input v-model="addUserForm.password" type="password"
                class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded px-2 py-1.5 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
            </div>
            <div>
              <label class="block text-slate-600 dark:text-slate-300 text-xs mb-1">Nome</label>
              <input v-model="addUserForm.nome"
                class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded px-2 py-1.5 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
            </div>
            <div>
              <label class="block text-slate-600 dark:text-slate-300 text-xs mb-1">E-mail</label>
              <input v-model="addUserForm.email" type="email"
                class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded px-2 py-1.5 text-sm outline-none focus:ring-2 focus:ring-violet-500" />
            </div>
            <div>
              <label class="block text-slate-600 dark:text-slate-300 text-xs mb-1">Role</label>
              <select v-model="addUserForm.role"
                class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded px-2 py-1.5 text-sm outline-none focus:ring-2 focus:ring-violet-500">
                <option value="MEMBER">MEMBER</option>
                <option value="OWNER">OWNER</option>
              </select>
            </div>
          </div>
          <div v-if="addUserError" class="text-red-500 text-xs">{{ addUserError }}</div>
          <div class="flex gap-2">
            <button @click="submitAddUser"
              :disabled="addUserSaving || !addUserForm.username.trim() || !addUserForm.password.trim()"
              class="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white px-4 py-1.5 rounded text-sm font-medium transition-colors">
              {{ addUserSaving ? 'Salvando...' : 'Adicionar' }}
            </button>
            <button @click="showAddUser = false" class="text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 text-sm px-3">Cancelar</button>
          </div>
        </div>

        <button
          v-if="!showAddUser"
          @click="showAddUser = true; addUserForm = { username: '', email: '', nome: '', password: '', role: 'MEMBER' }; addUserError = ''"
          class="mt-3 w-full border border-dashed border-violet-300 dark:border-violet-700 text-violet-600 dark:text-violet-400 hover:bg-violet-50 dark:hover:bg-violet-900/20 rounded-lg py-2 text-sm transition-colors"
        >
          + Adicionar usuário
        </button>
      </div>
    </div>

    <!-- Tabela -->
    <div class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-slate-400 text-sm">Carregando...</div>
      <div v-else-if="tenants.length === 0" class="p-8 text-center text-slate-400 text-sm">
        Nenhum tenant cadastrado
      </div>
      <table v-else class="w-full text-sm">
        <thead class="bg-slate-50 dark:bg-slate-700/50 border-b border-slate-200 dark:border-slate-700">
          <tr>
            <th class="text-left px-4 py-3 text-slate-500 dark:text-slate-400 font-medium">#</th>
            <th class="text-left px-4 py-3 text-slate-500 dark:text-slate-400 font-medium">Nome</th>
            <th class="text-left px-4 py-3 text-slate-500 dark:text-slate-400 font-medium">Descrição</th>
            <th class="text-left px-4 py-3 text-slate-500 dark:text-slate-400 font-medium">Criado em</th>
            <th class="px-4 py-3" />
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100 dark:divide-slate-700">
          <tr v-for="tenant in tenants" :key="tenant.id" class="hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
            <td class="px-4 py-3 text-slate-400 dark:text-slate-500">{{ tenant.id }}</td>
            <td class="px-4 py-3 font-medium text-slate-800 dark:text-slate-200">{{ tenant.nome }}</td>
            <td class="px-4 py-3 text-slate-500 dark:text-slate-400">{{ tenant.descricao ?? '—' }}</td>
            <td class="px-4 py-3 text-slate-400 dark:text-slate-500">
              {{ new Date(tenant.created_at).toLocaleDateString('pt-BR') }}
            </td>
            <td class="px-4 py-3">
              <div class="flex gap-3 justify-end">
                <button @click="openUsuarios(tenant)" class="text-violet-600 dark:text-violet-400 hover:text-violet-400 dark:hover:text-violet-300 text-xs font-medium">Usuários</button>
                <button @click="openEdit(tenant)" class="text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 text-xs font-medium">Editar</button>
                <button @click="remove(tenant.id)" class="text-red-500 hover:text-red-400 text-xs font-medium">Deletar</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
