<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { adminApi, type Tenant } from '@/api/adminClient'

const tenants = ref<Tenant[]>([])
const loading = ref(true)
const showForm = ref(false)
const editingId = ref<number | null>(null)
const form = ref({ nome: '', descricao: '' })
const saving = ref(false)
const error = ref('')

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
  editingId.value = null
  form.value = { nome: '', descricao: '' }
  showForm.value = true
}

function openEdit(tenant: Tenant) {
  editingId.value = tenant.id
  form.value = { nome: tenant.nome, descricao: tenant.descricao ?? '' }
  showForm.value = true
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    if (editingId.value) {
      await adminApi.updateTenant(editingId.value, form.value)
    } else {
      await adminApi.createTenant(form.value)
    }
    showForm.value = false
    await load()
  } catch {
    error.value = 'Erro ao salvar'
  } finally {
    saving.value = false
  }
}

async function remove(id: number) {
  if (!confirm('Deletar este tenant?')) return
  try {
    await adminApi.deleteTenant(id)
    await load()
  } catch {
    alert('Erro ao deletar')
  }
}
</script>

<template>
  <div class="p-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-slate-800 text-2xl font-bold">Tenants</h1>
        <p class="text-slate-500 text-sm mt-1">Organizações cadastradas no sistema</p>
      </div>
      <button
        @click="openCreate"
        class="bg-violet-600 hover:bg-violet-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
      >
        + Novo Tenant
      </button>
    </div>

    <!-- Modal form -->
    <div
      v-if="showForm"
      class="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
      @click.self="showForm = false"
    >
      <div class="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl">
        <h2 class="text-slate-800 font-semibold mb-4">
          {{ editingId ? 'Editar Tenant' : 'Novo Tenant' }}
        </h2>
        <div class="space-y-3">
          <div>
            <label class="block text-slate-600 text-sm mb-1">Nome</label>
            <input
              v-model="form.nome"
              class="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-400"
            />
          </div>
          <div>
            <label class="block text-slate-600 text-sm mb-1">Descrição</label>
            <input
              v-model="form.descricao"
              class="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-400"
            />
          </div>
          <div v-if="error" class="text-red-500 text-sm">{{ error }}</div>
        </div>
        <div class="flex gap-3 mt-5">
          <button
            @click="save"
            :disabled="saving"
            class="flex-1 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg py-2 text-sm font-medium transition-colors"
          >
            {{ saving ? 'Salvando...' : 'Salvar' }}
          </button>
          <button
            @click="showForm = false"
            class="flex-1 border border-slate-200 text-slate-600 hover:bg-slate-50 rounded-lg py-2 text-sm transition-colors"
          >
            Cancelar
          </button>
        </div>
      </div>
    </div>

    <!-- Table -->
    <div class="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-slate-400 text-sm">Carregando...</div>
      <div v-else-if="tenants.length === 0" class="p-8 text-center text-slate-400 text-sm">
        Nenhum tenant cadastrado
      </div>
      <table v-else class="w-full text-sm">
        <thead class="bg-slate-50 border-b border-slate-200">
          <tr>
            <th class="text-left px-4 py-3 text-slate-500 font-medium">#</th>
            <th class="text-left px-4 py-3 text-slate-500 font-medium">Nome</th>
            <th class="text-left px-4 py-3 text-slate-500 font-medium">Descrição</th>
            <th class="text-left px-4 py-3 text-slate-500 font-medium">Criado em</th>
            <th class="px-4 py-3" />
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <tr v-for="tenant in tenants" :key="tenant.id" class="hover:bg-slate-50 transition-colors">
            <td class="px-4 py-3 text-slate-400">{{ tenant.id }}</td>
            <td class="px-4 py-3 font-medium text-slate-800">{{ tenant.nome }}</td>
            <td class="px-4 py-3 text-slate-500">{{ tenant.descricao ?? '—' }}</td>
            <td class="px-4 py-3 text-slate-400">
              {{ new Date(tenant.created_at).toLocaleDateString('pt-BR') }}
            </td>
            <td class="px-4 py-3">
              <div class="flex gap-2 justify-end">
                <button
                  @click="openEdit(tenant)"
                  class="text-violet-600 hover:text-violet-400 text-xs font-medium"
                >
                  Editar
                </button>
                <button
                  @click="remove(tenant.id)"
                  class="text-red-500 hover:text-red-400 text-xs font-medium"
                >
                  Deletar
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
