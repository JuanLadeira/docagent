<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type ContatoDetalhe } from '@/api/client'

const route = useRoute()
const router = useRouter()
const contato = ref<ContatoDetalhe | null>(null)
const editando = ref(false)
const salvando = ref(false)
const editForm = ref({ nome: '', email: '', notas: '' })

async function carregar() {
  try {
    const r = await api.getContato(Number(route.params.id))
    contato.value = r.data
  } catch {
    router.push('/contatos')
  }
}

function abrirEdicao() {
  if (!contato.value) return
  editForm.value = {
    nome: contato.value.nome,
    email: contato.value.email ?? '',
    notas: contato.value.notas ?? '',
  }
  editando.value = true
}

async function salvar() {
  if (!contato.value || salvando.value) return
  salvando.value = true
  try {
    await api.atualizarContato(contato.value.id, {
      nome: editForm.value.nome.trim() || undefined,
      email: editForm.value.email.trim() || null,
      notas: editForm.value.notas.trim() || null,
    })
    await carregar()
    editando.value = false
  } finally {
    salvando.value = false
  }
}

function corStatus(status: string) {
  if (status === 'ATIVO') return 'bg-green-100 text-green-700'
  if (status === 'HUMANO') return 'bg-orange-100 text-orange-700'
  return 'bg-gray-100 text-gray-500'
}

function formatarData(iso: string) {
  return new Date(iso).toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(carregar)
</script>

<template>
  <div class="max-w-3xl mx-auto py-8 px-4">
    <!-- Voltar -->
    <button
      class="text-sm text-gray-500 hover:text-gray-700 mb-6 flex items-center gap-1 transition-colors"
      @click="router.push('/contatos')"
    >
      ← Contatos
    </button>

    <div v-if="!contato" class="text-sm text-gray-400 text-center py-8">Carregando...</div>

    <template v-else>
      <!-- Cabeçalho do contato -->
      <div class="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <div class="flex items-start justify-between">
          <div>
            <h1 class="text-xl font-bold text-gray-800">{{ contato.nome }}</h1>
            <div class="text-sm text-gray-500 mt-0.5">{{ contato.numero }}</div>
            <div v-if="contato.email" class="text-sm text-gray-400 mt-0.5">{{ contato.email }}</div>
          </div>
          <button
            class="px-3 py-1.5 text-xs font-medium rounded-lg bg-indigo-100 text-indigo-700 hover:bg-indigo-200 transition-colors"
            @click="abrirEdicao"
          >
            Editar
          </button>
        </div>
        <div v-if="contato.notas" class="mt-3 p-3 bg-gray-50 rounded-lg text-sm text-gray-600 whitespace-pre-wrap">
          {{ contato.notas }}
        </div>
      </div>

      <!-- Formulário de edição -->
      <div v-if="editando" class="bg-white rounded-xl border border-indigo-200 p-6 mb-6">
        <h2 class="text-sm font-semibold text-gray-700 mb-4">Editar contato</h2>
        <div class="space-y-3">
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">Nome *</label>
            <input
              v-model="editForm.nome"
              type="text"
              class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">E-mail</label>
            <input
              v-model="editForm.email"
              type="email"
              class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">Notas</label>
            <textarea
              v-model="editForm.notas"
              rows="3"
              class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            />
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-4">
          <button
            class="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800 transition-colors"
            @click="editando = false"
          >
            Cancelar
          </button>
          <button
            class="px-4 py-1.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
            :disabled="salvando || !editForm.nome.trim()"
            @click="salvar"
          >
            {{ salvando ? 'Salvando...' : 'Salvar' }}
          </button>
        </div>
      </div>

      <!-- Histórico de atendimentos -->
      <div>
        <h2 class="text-sm font-semibold text-gray-700 mb-3">
          Histórico de atendimentos ({{ contato.atendimentos.length }})
        </h2>

        <div v-if="contato.atendimentos.length === 0" class="text-sm text-gray-400 text-center py-6">
          Nenhum atendimento registrado
        </div>

        <div v-else class="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
          <button
            v-for="at in contato.atendimentos"
            :key="at.id"
            class="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors text-left"
            @click="router.push('/atendimentos')"
          >
            <div class="flex items-center gap-2">
              <span
                class="text-xs px-2 py-0.5 rounded font-medium"
                :class="corStatus(at.status)"
              >
                {{ at.status }}
              </span>
              <span class="text-sm text-gray-600">{{ formatarData(at.created_at) }}</span>
            </div>
          </button>
        </div>
      </div>
    </template>
  </div>
</template>
