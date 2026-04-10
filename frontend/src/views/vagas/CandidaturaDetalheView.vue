<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { vagasApi, type Candidatura, type CandidaturaStatus } from '@/api/vagas'

const route = useRoute()
const router = useRouter()
const candidaturaId = Number(route.params.id)

const candidatura = ref<Candidatura | null>(null)
const carregando = ref(true)
const atualizando = ref(false)
const erro = ref('')
const runId = ref<number | null>(null)

onMounted(async () => {
  try {
    const r = await vagasApi.getCandidatura(candidaturaId)
    candidatura.value = r.data
    runId.value = r.data.pipeline_run_id
  } catch {
    erro.value = 'Candidatura não encontrada.'
  } finally {
    carregando.value = false
  }
})

async function marcarStatus(status: CandidaturaStatus) {
  if (!candidatura.value || atualizando.value) return
  atualizando.value = true
  try {
    const r = await vagasApi.atualizarStatusCandidatura(candidaturaId, status)
    candidatura.value = r.data
  } catch {
    erro.value = 'Falha ao atualizar status.'
  } finally {
    atualizando.value = false
  }
}

function statusLabel(s: string) {
  const m: Record<string, string> = {
    AGUARDANDO_ENVIO: 'Aguardando envio',
    ENVIADA: 'Enviada',
    REJEITADA: 'Rejeitada',
  }
  return m[s] ?? s
}

function statusClass(s: string) {
  if (s === 'ENVIADA') return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
  if (s === 'REJEITADA') return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
  return 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
}

function copiar(texto: string) {
  navigator.clipboard.writeText(texto)
}

const baixandoPdf = ref(false)

async function baixarPdf() {
  if (baixandoPdf.value) return
  baixandoPdf.value = true
  try {
    const r = await vagasApi.downloadPdfCandidatura(candidaturaId)
    const url = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `candidatura_${candidaturaId}.pdf`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    erro.value = 'Falha ao gerar PDF.'
  } finally {
    baixandoPdf.value = false
  }
}
</script>

<template>
  <div class="flex flex-col h-full overflow-auto bg-gray-50 dark:bg-slate-950 p-6 gap-6">
    <!-- Cabeçalho -->
    <div class="flex items-center gap-3">
      <button
        @click="runId ? router.push({ name: 'pipeline-detalhe', params: { id: runId } }) : router.push({ name: 'vagas' })"
        class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
      >
        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
      </button>
      <div>
        <h1 class="text-xl font-bold text-slate-800 dark:text-slate-100">Candidatura #{{ candidaturaId }}</h1>
        <div class="flex items-center gap-2 mt-1">
          <span
            v-if="candidatura"
            class="text-xs font-medium px-2 py-0.5 rounded-full"
            :class="statusClass(candidatura.status)"
          >
            {{ statusLabel(candidatura.status) }}
          </span>
          <span
            v-if="candidatura?.simplificada"
            class="text-xs font-medium px-2 py-0.5 rounded-full bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400"
          >
            Simplificada
          </span>
        </div>
      </div>
    </div>

    <div v-if="carregando" class="text-center text-slate-400 text-sm py-10">Carregando...</div>
    <div v-else-if="erro" class="text-center text-red-500 text-sm py-10">{{ erro }}</div>

    <template v-else-if="candidatura">
      <!-- Ações -->
      <div class="flex items-center gap-3 flex-wrap">
        <!-- Download PDF -->
        <button
          :disabled="baixandoPdf"
          @click="baixarPdf"
          class="px-4 py-2 rounded-lg text-sm font-semibold bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors flex items-center gap-2"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          {{ baixandoPdf ? 'Gerando...' : 'Baixar PDF' }}
        </button>

        <button
          v-if="candidatura.status !== 'ENVIADA'"
          :disabled="atualizando"
          @click="marcarStatus('ENVIADA')"
          class="px-4 py-2 rounded-lg text-sm font-semibold bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 transition-colors"
        >
          Marcar como enviada
        </button>
        <button
          v-if="candidatura.status !== 'REJEITADA'"
          :disabled="atualizando"
          @click="marcarStatus('REJEITADA')"
          class="px-4 py-2 rounded-lg text-sm font-semibold bg-red-100 text-red-700 hover:bg-red-200 dark:bg-red-900/30 dark:text-red-400 dark:hover:bg-red-900/50 disabled:opacity-50 transition-colors"
        >
          Rejeitar
        </button>
        <p v-if="erro" class="text-xs text-red-500">{{ erro }}</p>
      </div>

      <!-- Resumo personalizado -->
      <div class="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-sm font-semibold text-slate-700 dark:text-slate-200">Resumo personalizado</h2>
          <button
            @click="copiar(candidatura.resumo_personalizado)"
            class="text-xs text-indigo-500 hover:text-indigo-700"
            title="Copiar"
          >
            Copiar
          </button>
        </div>
        <p
          v-if="candidatura.resumo_personalizado"
          class="text-sm text-slate-600 dark:text-slate-300 whitespace-pre-wrap leading-relaxed"
        >{{ candidatura.resumo_personalizado }}</p>
        <p v-else class="text-sm text-slate-400 italic">Nenhum resumo gerado.</p>
      </div>

      <!-- Carta de apresentação -->
      <div class="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-sm font-semibold text-slate-700 dark:text-slate-200">Carta de apresentação</h2>
          <button
            @click="copiar(candidatura.carta_apresentacao)"
            class="text-xs text-indigo-500 hover:text-indigo-700"
            title="Copiar"
          >
            Copiar
          </button>
        </div>
        <p
          v-if="candidatura.carta_apresentacao"
          class="text-sm text-slate-600 dark:text-slate-300 whitespace-pre-wrap leading-relaxed"
        >{{ candidatura.carta_apresentacao }}</p>
        <p v-else class="text-sm text-slate-400 italic">Nenhuma carta gerada.</p>
      </div>
    </template>
  </div>
</template>
