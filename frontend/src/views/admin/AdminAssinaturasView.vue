<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { adminApi, type Assinatura, type Tenant, type Plano } from '@/api/adminClient'

const assinaturas = ref<Assinatura[]>([])
const tenants = ref<Tenant[]>([])
const planos = ref<Plano[]>([])
const loading = ref(true)

const showAssign = ref(false)
const assignForm = ref({ tenant_id: 0, plano_id: 0 })
const assigning = ref(false)
const assignError = ref('')

const tenantsComAssinatura = computed(() => new Set(assinaturas.value.map(a => a.tenant_id)))
const tenantsSemAssinatura = computed(() => tenants.value.filter(t => !tenantsComAssinatura.value.has(t.id)))

async function load() {
  loading.value = true
  try {
    const [resA, resT, resP] = await Promise.all([
      adminApi.getAssinaturas(),
      adminApi.getTenants(),
      adminApi.getPlanos(),
    ])
    assinaturas.value = resA.data
    tenants.value = resT.data
    planos.value = resP.data
  } finally {
    loading.value = false
  }
}

onMounted(load)

function openAssign(tenantId?: number) {
  assignForm.value = {
    tenant_id: tenantId ?? (tenantsSemAssinatura.value[0]?.id ?? 0),
    plano_id: planos.value[0]?.id ?? 0,
  }
  assignError.value = ''
  showAssign.value = true
}

async function submitAssign() {
  if (!assignForm.value.tenant_id || !assignForm.value.plano_id) return
  assigning.value = true
  assignError.value = ''
  try {
    await adminApi.assignAssinatura(assignForm.value.tenant_id, assignForm.value.plano_id)
    showAssign.value = false
    await load()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    assignError.value = msg || 'Erro ao atribuir plano'
  } finally {
    assigning.value = false
  }
}

function tenantNome(tenantId: number) {
  return tenants.value.find(t => t.id === tenantId)?.nome ?? `Tenant #${tenantId}`
}
</script>

<template>
  <div class="p-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-slate-800 dark:text-slate-100 text-2xl font-bold">Assinaturas</h1>
        <p class="text-slate-500 dark:text-slate-400 text-sm mt-1">Planos atribuídos a cada tenant</p>
      </div>
      <button
        @click="openAssign()"
        :disabled="planos.length === 0"
        class="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
      >
        + Atribuir Plano
      </button>
    </div>

    <!-- Aviso: sem planos -->
    <div v-if="!loading && planos.length === 0"
      class="mb-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 text-amber-700 dark:text-amber-400 rounded-lg px-4 py-3 text-sm">
      Nenhum plano cadastrado. Crie planos na aba <strong>Planos</strong> antes de atribuir assinaturas.
    </div>

    <!-- Modal: atribuir plano -->
    <div v-if="showAssign" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="showAssign = false">
      <div class="bg-white dark:bg-slate-800 rounded-2xl p-6 w-full max-w-sm shadow-xl">
        <h2 class="text-slate-800 dark:text-slate-100 font-semibold mb-4">Atribuir Plano a Tenant</h2>
        <div class="space-y-3">
          <div>
            <label class="block text-slate-600 dark:text-slate-300 text-sm mb-1">Tenant</label>
            <select v-model.number="assignForm.tenant_id"
              class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500">
              <option :value="0" disabled>Selecione...</option>
              <option v-for="t in tenants" :key="t.id" :value="t.id">
                {{ t.nome }}<template v-if="tenantsComAssinatura.has(t.id)"> (troca de plano)</template>
              </option>
            </select>
          </div>
          <div>
            <label class="block text-slate-600 dark:text-slate-300 text-sm mb-1">Plano</label>
            <select v-model.number="assignForm.plano_id"
              class="w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-500">
              <option :value="0" disabled>Selecione...</option>
              <option v-for="p in planos" :key="p.id" :value="p.id">{{ p.nome }}</option>
            </select>
          </div>
          <div v-if="assignError" class="text-red-500 text-sm">{{ assignError }}</div>
        </div>
        <div class="flex gap-3 mt-5">
          <button @click="submitAssign" :disabled="assigning || !assignForm.tenant_id || !assignForm.plano_id"
            class="flex-1 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg py-2 text-sm font-medium transition-colors">
            {{ assigning ? 'Salvando...' : 'Atribuir' }}
          </button>
          <button @click="showAssign = false"
            class="flex-1 border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 rounded-lg py-2 text-sm transition-colors">
            Cancelar
          </button>
        </div>
      </div>
    </div>

    <!-- Tabela -->
    <div class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-slate-400 text-sm">Carregando...</div>
      <div v-else-if="assinaturas.length === 0" class="p-8 text-center text-slate-400 text-sm">
        Nenhuma assinatura atribuída
      </div>
      <table v-else class="w-full text-sm">
        <thead class="bg-slate-50 dark:bg-slate-700/50 border-b border-slate-200 dark:border-slate-700">
          <tr>
            <th class="text-left px-4 py-3 text-slate-500 dark:text-slate-400 font-medium">Tenant</th>
            <th class="text-left px-4 py-3 text-slate-500 dark:text-slate-400 font-medium">Plano</th>
            <th class="text-left px-4 py-3 text-slate-500 dark:text-slate-400 font-medium">Status</th>
            <th class="text-left px-4 py-3 text-slate-500 dark:text-slate-400 font-medium">Início</th>
            <th class="text-left px-4 py-3 text-slate-500 dark:text-slate-400 font-medium">Renovação</th>
            <th class="px-4 py-3" />
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100 dark:divide-slate-700">
          <tr v-for="a in assinaturas" :key="a.id" class="hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
            <td class="px-4 py-3 font-medium text-slate-800 dark:text-slate-200">
              {{ a.tenant_nome ?? tenantNome(a.tenant_id) }}
            </td>
            <td class="px-4 py-3 text-slate-700 dark:text-slate-300">{{ a.plano_nome }}</td>
            <td class="px-4 py-3">
              <span class="text-xs px-2 py-0.5 rounded-full font-medium"
                :class="a.ativo ? 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400' : 'bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400'">
                {{ a.ativo ? 'Ativa' : 'Inativa' }}
              </span>
            </td>
            <td class="px-4 py-3 text-slate-400 dark:text-slate-500">{{ new Date(a.data_inicio).toLocaleDateString('pt-BR') }}</td>
            <td class="px-4 py-3 text-slate-400 dark:text-slate-500">{{ new Date(a.data_proxima_renovacao).toLocaleDateString('pt-BR') }}</td>
            <td class="px-4 py-3">
              <button @click="openAssign(a.tenant_id)" class="text-violet-600 dark:text-violet-400 hover:text-violet-400 dark:hover:text-violet-300 text-xs font-medium">
                Trocar plano
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Tenants sem assinatura -->
    <div v-if="!loading && tenantsSemAssinatura.length > 0" class="mt-6">
      <p class="text-slate-500 dark:text-slate-400 text-sm font-medium mb-3">
        Tenants sem assinatura ({{ tenantsSemAssinatura.length }})
      </p>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="t in tenantsSemAssinatura" :key="t.id"
          @click="openAssign(t.id)"
          class="border border-dashed border-slate-300 dark:border-slate-600 text-slate-500 dark:text-slate-400 hover:border-violet-400 dark:hover:border-violet-500 hover:text-violet-600 dark:hover:text-violet-400 rounded-lg px-3 py-1.5 text-xs transition-colors"
        >
          {{ t.nome }} — atribuir plano
        </button>
      </div>
    </div>
  </div>
</template>
