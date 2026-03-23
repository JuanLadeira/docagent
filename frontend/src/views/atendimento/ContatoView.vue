<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { api, type Contato } from '@/api/client'

const router = useRouter()
const contatos = ref<Contato[]>([])
const busca = ref('')
const carregando = ref(false)

async function carregar() {
  carregando.value = true
  try {
    const r = await api.listContatos()
    contatos.value = r.data
  } finally {
    carregando.value = false
  }
}

const contatosFiltrados = computed(() => {
  const q = busca.value.toLowerCase().trim()
  if (!q) return contatos.value
  return contatos.value.filter(
    (c) => c.nome.toLowerCase().includes(q) || c.numero.includes(q),
  )
})

function formatarData(iso: string) {
  return new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit' })
}

onMounted(carregar)
</script>

<template>
  <div class="max-w-3xl mx-auto py-8 px-4">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-xl font-bold text-gray-800">Contatos</h1>
    </div>

    <!-- Busca -->
    <div class="mb-4">
      <input
        v-model="busca"
        type="text"
        placeholder="Buscar por nome ou número..."
        class="w-full px-4 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
      />
    </div>

    <!-- Loading -->
    <div v-if="carregando" class="text-sm text-gray-400 text-center py-8">Carregando...</div>

    <!-- Vazio -->
    <div v-else-if="contatosFiltrados.length === 0" class="text-sm text-gray-400 text-center py-8">
      {{ busca ? 'Nenhum contato encontrado' : 'Nenhum contato cadastrado' }}
    </div>

    <!-- Lista -->
    <div v-else class="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
      <button
        v-for="contato in contatosFiltrados"
        :key="contato.id"
        class="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors text-left"
        @click="router.push(`/contatos/${contato.id}`)"
      >
        <div>
          <div class="text-sm font-medium text-gray-800">{{ contato.nome }}</div>
          <div class="text-xs text-gray-500">{{ contato.numero }}</div>
          <div v-if="contato.email" class="text-xs text-gray-400">{{ contato.email }}</div>
        </div>
        <div class="text-xs text-gray-400">
          {{ formatarData(contato.created_at) }}
        </div>
      </button>
    </div>
  </div>
</template>
