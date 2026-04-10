<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { vagasApi, subscribePipelineEventos, type PipelineRunDetalhe, type PipelineEvent } from '@/api/vagas'

const route = useRoute()
const router = useRouter()
const runId = Number(route.params.id)

const run = ref<PipelineRunDetalhe | null>(null)
const carregando = ref(true)
const eventos = ref<{ texto: string; tipo: string }[]>([])
const concluido = ref(false)
const minScore = ref(0.0)
const fonteAtiva = ref<string>('TODAS')
let sseCleanup: (() => void) | null = null

const FONTES = ['GUPY', 'DUCKDUCKGO', 'LINKEDIN', 'INDEED'] as const

const statsPorFonte = computed(() => {
  const vagas = run.value?.vagas ?? []
  return FONTES.map((fonte) => {
    const vagsF = vagas.filter((v) => v.fonte === fonte)
    const melhorScore = vagsF.length ? Math.max(...vagsF.map((v) => v.match_score)) : 0
    return { fonte, count: vagsF.length, melhorScore }
  }).filter((s) => s.count > 0)
})

const vagasFiltradas = computed(() => {
  const base = (run.value?.vagas ?? []).filter((v) => v.match_score >= minScore.value)
  if (fonteAtiva.value === 'TODAS') return base
  return base.filter((v) => v.fonte === fonteAtiva.value)
})

async function carregar() {
  carregando.value = true
  try {
    const r = await vagasApi.getPipelineDetalhe(runId)
    run.value = r.data
    if (['CONCLUIDO', 'ERRO'].includes(r.data.status)) {
      concluido.value = true
    }
  } catch {
    eventos.value.push({ texto: 'Falha ao carregar pipeline.', tipo: 'ERRO' })
  } finally {
    carregando.value = false
  }
}

function handleEvento(event: PipelineEvent) {
  if (event.type === 'ping') return

  if (event.type === 'PROGRESSO') {
    eventos.value.push({ texto: event.mensagem, tipo: 'PROGRESSO' })
  } else if (event.type === 'CONCLUIDO') {
    eventos.value.push({
      texto: `Concluído! ${event.vagas_encontradas} vagas encontradas, ${event.candidaturas_criadas} candidaturas geradas.`,
      tipo: 'CONCLUIDO',
    })
    concluido.value = true
    carregar()
  } else if (event.type === 'ERRO') {
    eventos.value.push({ texto: `Erro: ${event.mensagem}`, tipo: 'ERRO' })
    concluido.value = true
    carregar()
  }
}

onMounted(async () => {
  await carregar()
  if (!concluido.value) {
    sseCleanup = subscribePipelineEventos(runId, handleEvento, () => {
      if (!concluido.value) carregar()
    })
  }
})

onUnmounted(() => sseCleanup?.())

function scoreBar(score: number) {
  if (score >= 0.8) return 'bg-emerald-500'
  if (score >= 0.5) return 'bg-amber-500'
  return 'bg-slate-400'
}

function scoreText(score: number) {
  return Math.round(score * 100) + '%'
}

function fonteIcon(fonte: string): string {
  const m: Record<string, string> = { GUPY: '🚀', DUCKDUCKGO: '🦆', LINKEDIN: '💼', INDEED: '🔍' }
  return m[fonte] ?? '🌐'
}

function statusLabel(s: string): string {
  const m: Record<string, string> = {
    PENDENTE: 'Pendente', ANALISANDO_CV: 'Analisando CV',
    BUSCANDO_VAGAS: 'Buscando vagas', PERSONALIZANDO: 'Personalizando',
    REGISTRANDO: 'Registrando', CONCLUIDO: 'Concluído', ERRO: 'Erro',
  }
  return m[s] ?? s
}

function candidaturaParaVaga(vagaId: number) {
  return run.value?.candidaturas.find((c) => c.vaga_id === vagaId)
}
</script>

<template>
  <div class="flex flex-col h-full overflow-auto bg-gray-50 dark:bg-slate-950 p-6 gap-6">
    <!-- Cabeçalho -->
    <div class="flex items-center gap-3">
      <button
        @click="router.push({ name: 'vagas' })"
        class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
      >
        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
      </button>
      <div>
        <h1 class="text-xl font-bold text-slate-800 dark:text-slate-100">Pipeline #{{ runId }}</h1>
        <p v-if="run" class="text-xs text-slate-400">{{ statusLabel(run.status) }}</p>
      </div>
    </div>

    <!-- Progresso SSE (enquanto em execução) -->
    <div
      v-if="!concluido || eventos.length > 0"
      class="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700 p-5"
    >
      <h2 class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">Progresso</h2>

      <div v-if="eventos.length === 0 && !concluido" class="flex items-center gap-2 text-sm text-slate-400">
        <svg class="animate-spin w-4 h-4 text-indigo-500" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
        </svg>
        Aguardando eventos...
      </div>

      <ul class="space-y-1.5">
        <li
          v-for="(ev, i) in eventos"
          :key="i"
          class="flex items-start gap-2 text-sm"
          :class="{
            'text-emerald-600 dark:text-emerald-400': ev.tipo === 'CONCLUIDO',
            'text-red-600 dark:text-red-400': ev.tipo === 'ERRO',
            'text-slate-600 dark:text-slate-300': ev.tipo === 'PROGRESSO',
          }"
        >
          <span class="mt-0.5">
            {{ ev.tipo === 'CONCLUIDO' ? '✅' : ev.tipo === 'ERRO' ? '❌' : '⏳' }}
          </span>
          <span>{{ ev.texto }}</span>
        </li>
      </ul>

      <!-- Spinner enquanto não concluído -->
      <div v-if="!concluido" class="mt-3 flex items-center gap-2 text-xs text-slate-400">
        <svg class="animate-spin w-3 h-3 text-indigo-500" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
        </svg>
        Processando...
      </div>
    </div>

    <!-- Erro do pipeline -->
    <div
      v-if="run?.erro"
      class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-5"
    >
      <p class="text-sm font-semibold text-red-700 dark:text-red-400">Erro no pipeline</p>
      <p class="text-xs text-red-600 dark:text-red-300 mt-1">{{ run.erro }}</p>
    </div>

    <!-- Stats por fonte -->
    <div v-if="statsPorFonte.length > 0" class="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <button
        v-for="s in statsPorFonte"
        :key="s.fonte"
        @click="fonteAtiva = fonteAtiva === s.fonte ? 'TODAS' : s.fonte"
        class="rounded-xl border p-4 text-left transition cursor-pointer"
        :class="fonteAtiva === s.fonte
          ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/30'
          : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 hover:border-indigo-300 dark:hover:border-indigo-700'"
      >
        <p class="text-xl leading-none">{{ fonteIcon(s.fonte) }}</p>
        <p class="text-xs font-semibold text-slate-600 dark:text-slate-300 mt-2">{{ s.fonte }}</p>
        <p class="text-2xl font-bold text-indigo-600 dark:text-indigo-400 leading-tight">{{ s.count }}</p>
        <p class="text-xs text-slate-400 mt-0.5">melhor: {{ Math.round(s.melhorScore * 100) }}%</p>
      </button>
    </div>

    <!-- Vagas -->
    <div
      v-if="run && run.vagas.length > 0"
      class="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700"
    >
      <div class="px-6 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between gap-4 flex-wrap">
        <h2 class="text-base font-semibold text-slate-700 dark:text-slate-200 whitespace-nowrap">
          Vagas ({{ vagasFiltradas.length }}<span v-if="fonteAtiva !== 'TODAS'" class="text-indigo-500"> · {{ fonteAtiva }}</span>)
        </h2>
        <div class="flex items-center gap-3 flex-wrap">
          <button
            v-if="fonteAtiva !== 'TODAS'"
            @click="fonteAtiva = 'TODAS'"
            class="text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
          >
            ✕ limpar filtro
          </button>
          <div class="flex items-center gap-2 text-xs text-slate-500">
            <label>Score mín.</label>
            <select
              v-model.number="minScore"
              class="text-xs rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 px-2 py-1"
            >
              <option :value="0.0">Todos</option>
              <option :value="0.3">30%+</option>
              <option :value="0.5">50%+</option>
              <option :value="0.7">70%+</option>
              <option :value="0.9">90%+</option>
            </select>
          </div>
        </div>
      </div>

      <ul class="divide-y divide-slate-100 dark:divide-slate-800">
        <li
          v-for="vaga in vagasFiltradas"
          :key="vaga.id"
          class="px-6 py-4"
        >
          <div class="flex items-start justify-between gap-4">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-sm font-semibold text-slate-800 dark:text-slate-100">{{ vaga.titulo }}</span>
                <span class="text-xs text-slate-400">{{ fonteIcon(vaga.fonte) }} {{ vaga.fonte }}</span>
                <span
                  v-if="vaga.candidatura_simplificada"
                  class="text-xs font-medium px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                  title="Esta vaga aceita candidatura simplificada / Easy Apply"
                >
                  ⚡ Easy Apply
                </span>
              </div>
              <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                {{ vaga.empresa }} · {{ vaga.localizacao }}
              </p>
              <p class="text-xs text-slate-400 mt-1 line-clamp-2">{{ vaga.descricao }}</p>
            </div>

            <!-- Score -->
            <div class="flex flex-col items-end gap-1 shrink-0">
              <span class="text-sm font-bold" :class="{
                'text-emerald-600': vaga.match_score >= 0.8,
                'text-amber-600': vaga.match_score >= 0.5 && vaga.match_score < 0.8,
                'text-slate-500': vaga.match_score < 0.5,
              }">{{ scoreText(vaga.match_score) }}</span>
              <div class="w-16 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                <div
                  class="h-full rounded-full"
                  :class="scoreBar(vaga.match_score)"
                  :style="{ width: scoreText(vaga.match_score) }"
                />
              </div>
            </div>
          </div>

          <!-- Ações -->
          <div class="flex items-center gap-3 mt-3">
            <a
              :href="vaga.url"
              target="_blank"
              rel="noopener"
              class="text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
            >
              Ver vaga ↗
            </a>
            <button
              v-if="candidaturaParaVaga(vaga.id)"
              @click="router.push({ name: 'candidatura-detalhe', params: { id: candidaturaParaVaga(vaga.id)!.id } })"
              class="text-xs text-emerald-600 dark:text-emerald-400 hover:underline"
            >
              Ver candidatura →
            </button>
          </div>
        </li>
      </ul>
    </div>

    <!-- Loading -->
    <div v-if="carregando" class="text-center text-slate-400 text-sm py-8">Carregando...</div>
  </div>
</template>
