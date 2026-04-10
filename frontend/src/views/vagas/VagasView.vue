<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  vagasApi,
  defaultConfig,
  FONTES_DISPONIVEIS,
  type PipelineRun,
  type PipelineConfig,
  type CandidatoPerfil,
} from '@/api/vagas'

const router = useRouter()

const pipelines = ref<PipelineRun[]>([])
const candidatos = ref<CandidatoPerfil[]>([])
const carregando = ref(false)
const enviando = ref(false)
const erro = ref('')
const cvFile = ref<File | null>(null)
const dragOver = ref(false)
const mostrarConfig = ref(false)
const config = ref<PipelineConfig>(defaultConfig())

// Filtro de candidato selecionado
const candidatoFiltro = ref<number | null>(null)
const candidatoReuso = ref<CandidatoPerfil | null>(null)  // perfil selecionado para reuso
const configReuso = ref<PipelineConfig>(defaultConfig())
const iniciandoReuso = ref(false)
const erroReuso = ref('')

const pipelinesFiltrados = computed(() => {
  if (candidatoFiltro.value === null) return pipelines.value
  return pipelines.value.filter((p) => p.candidato_id === candidatoFiltro.value)
})

const FONTE_LABELS: Record<string, string> = {
  GUPY: 'Gupy',
  DUCKDUCKGO: 'DuckDuckGo',
  LINKEDIN: 'LinkedIn',
  INDEED: 'Indeed',
}

async function carregar() {
  carregando.value = true
  try {
    const [rPipelines, rCandidatos] = await Promise.all([
      vagasApi.listarPipelines(),
      vagasApi.listarCandidatos(),
    ])
    pipelines.value = rPipelines.data.sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    )
    candidatos.value = rCandidatos.data.sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    )
  } catch {
    erro.value = 'Falha ao carregar dados.'
  } finally {
    carregando.value = false
  }
}

onMounted(carregar)

function onFileInput(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files?.[0]) cvFile.value = target.files[0]
}

function onDrop(e: DragEvent) {
  dragOver.value = false
  const file = e.dataTransfer?.files[0]
  if (file && file.type === 'application/pdf') cvFile.value = file
}

function toggleFonte(fonte: string) {
  const idx = config.value.fontes.indexOf(fonte as never)
  if (idx >= 0) {
    if (config.value.fontes.length > 1) config.value.fontes.splice(idx, 1)
  } else {
    config.value.fontes.push(fonte as never)
  }
}

function selecionarCandidato(id: number) {
  candidatoFiltro.value = candidatoFiltro.value === id ? null : id
}

function abrirReuso(c: CandidatoPerfil) {
  candidatoReuso.value = c
  configReuso.value = defaultConfig()
  erroReuso.value = ''
}

function fecharReuso() {
  candidatoReuso.value = null
  erroReuso.value = ''
}

function toggleFonteReuso(fonte: string) {
  const idx = configReuso.value.fontes.indexOf(fonte as never)
  if (idx >= 0) {
    if (configReuso.value.fontes.length > 1) configReuso.value.fontes.splice(idx, 1)
  } else {
    configReuso.value.fontes.push(fonte as never)
  }
}

async function iniciarReuso() {
  if (!candidatoReuso.value || iniciandoReuso.value) return
  iniciandoReuso.value = true
  erroReuso.value = ''
  try {
    const r = await vagasApi.reutilizarPipeline(candidatoReuso.value.id, configReuso.value)
    router.push({ name: 'pipeline-detalhe', params: { id: r.data.pipeline_run_id } })
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    erroReuso.value = msg || 'Erro ao iniciar pipeline.'
    iniciandoReuso.value = false
  }
}

function runsParaCandidato(candidatoId: number) {
  return pipelines.value.filter((p) => p.candidato_id === candidatoId).length
}

async function iniciarPipeline() {
  if (!cvFile.value || enviando.value) return
  enviando.value = true
  erro.value = ''
  try {
    const r = await vagasApi.iniciarPipeline(cvFile.value, config.value)
    router.push({ name: 'pipeline-detalhe', params: { id: r.data.pipeline_run_id } })
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    erro.value = msg || 'Erro ao iniciar pipeline.'
    enviando.value = false
  }
}

function statusLabel(s: string): string {
  const m: Record<string, string> = {
    PENDENTE: 'Pendente', ANALISANDO_CV: 'Analisando CV',
    BUSCANDO_VAGAS: 'Buscando vagas', PERSONALIZANDO: 'Personalizando',
    REGISTRANDO: 'Registrando', CONCLUIDO: 'Concluído', ERRO: 'Erro',
  }
  return m[s] ?? s
}

function statusClass(s: string): string {
  if (s === 'CONCLUIDO') return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
  if (s === 'ERRO') return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
  if (s === 'PENDENTE') return 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
  return 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400'
}

function formatData(iso: string) {
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function iniciais(nome: string) {
  return nome.split(' ').slice(0, 2).map((p) => p[0]).join('').toUpperCase()
}
</script>

<template>
  <div class="flex flex-col h-full overflow-auto bg-gray-50 dark:bg-slate-950 p-6 gap-6">
    <!-- Cabeçalho -->
    <div>
      <h1 class="text-2xl font-bold text-slate-800 dark:text-slate-100">Busca de Vagas</h1>
      <p class="text-sm text-slate-500 dark:text-slate-400 mt-1">
        Envie seu currículo e deixe os agentes encontrarem e personalizarem vagas para você.
      </p>
    </div>

    <!-- Perfis de candidato -->
    <div v-if="candidatos.length > 0" class="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-sm font-semibold text-slate-700 dark:text-slate-200">Perfis</h2>
        <button
          v-if="candidatoFiltro !== null"
          @click="candidatoFiltro = null"
          class="text-xs text-indigo-500 hover:text-indigo-700"
        >
          Limpar filtro
        </button>
      </div>

      <div class="flex flex-wrap gap-3">
        <div
          v-for="c in candidatos"
          :key="c.id"
          class="flex items-center gap-3 px-3 py-2.5 rounded-xl border transition-all"
          :class="
            candidatoFiltro === c.id
              ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-950/30'
              : 'border-slate-200 dark:border-slate-700'
          "
        >
          <!-- Avatar clicável = filtro -->
          <button @click="selecionarCandidato(c.id)" class="flex items-center gap-3 min-w-0">
            <div
              class="w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold text-white shrink-0"
              :class="candidatoFiltro === c.id ? 'bg-indigo-600' : 'bg-slate-400 dark:bg-slate-600'"
            >
              {{ iniciais(c.nome || 'C') }}
            </div>
            <div class="text-left min-w-0">
              <p class="text-sm font-medium text-slate-800 dark:text-slate-100 leading-tight truncate max-w-[140px]">
                {{ c.nome || c.cv_filename }}
              </p>
              <p class="text-xs text-slate-400 leading-tight mt-0.5">
                {{ c.cargo_desejado || 'Cargo não identificado' }}
                <span v-if="runsParaCandidato(c.id)" class="ml-1 text-indigo-400">
                  · {{ runsParaCandidato(c.id) }} pipeline{{ runsParaCandidato(c.id) !== 1 ? 's' : '' }}
                </span>
              </p>
            </div>
          </button>

          <!-- Botão novo pipeline para este perfil -->
          <button
            @click="abrirReuso(c)"
            class="ml-2 shrink-0 w-7 h-7 rounded-full bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-200 dark:hover:bg-indigo-800 flex items-center justify-center transition-colors"
            title="Novo pipeline para este perfil"
          >
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 4v16m8-8H4" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Painel de reuso inline -->
      <div
        v-if="candidatoReuso"
        class="mt-5 rounded-xl border border-indigo-200 dark:border-indigo-800 bg-indigo-50 dark:bg-indigo-950/20 p-5"
      >
        <div class="flex items-center justify-between mb-4">
          <p class="text-sm font-semibold text-indigo-700 dark:text-indigo-300">
            Novo pipeline — {{ candidatoReuso.nome || candidatoReuso.cv_filename }}
          </p>
          <button @click="fecharReuso" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <p class="text-xs text-indigo-600 dark:text-indigo-400 mb-4">
          Vagas já encontradas em runs anteriores serão excluídas automaticamente da nova busca.
        </p>

        <!-- Fontes -->
        <div class="mb-3">
          <p class="text-xs font-semibold text-slate-600 dark:text-slate-300 mb-2">Origens de busca</p>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="fonte in FONTES_DISPONIVEIS"
              :key="fonte"
              @click="toggleFonteReuso(fonte)"
              class="px-3 py-1.5 rounded-full text-xs font-medium border transition-colors"
              :class="
                configReuso.fontes.includes(fonte)
                  ? 'bg-indigo-600 text-white border-indigo-600'
                  : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-300 dark:border-slate-600'
              "
            >
              {{ FONTE_LABELS[fonte] }}
            </button>
          </div>
        </div>

        <!-- Quantidades -->
        <div class="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label class="text-xs font-semibold text-slate-600 dark:text-slate-300 block mb-1">Máx. por fonte (1-50)</label>
            <input v-model.number="configReuso.max_vagas_por_fonte" type="number" min="1" max="50"
              class="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-sm text-slate-700 dark:text-slate-200 px-3 py-1.5" />
          </div>
          <div>
            <label class="text-xs font-semibold text-slate-600 dark:text-slate-300 block mb-1">Máx. candidaturas (1-20)</label>
            <input v-model.number="configReuso.max_personalizar" type="number" min="1" max="20"
              class="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-sm text-slate-700 dark:text-slate-200 px-3 py-1.5" />
          </div>
        </div>

        <!-- Toggles -->
        <div class="flex flex-col gap-2 mb-4">
          <label class="flex items-center gap-2 cursor-pointer">
            <div class="relative">
              <input type="checkbox" v-model="configReuso.apenas_simplificadas" class="sr-only" />
              <div class="w-8 h-4 rounded-full transition-colors" :class="configReuso.apenas_simplificadas ? 'bg-indigo-600' : 'bg-slate-300 dark:bg-slate-600'" />
              <div class="absolute top-0 left-0 w-4 h-4 rounded-full bg-white shadow transition-transform" :class="configReuso.apenas_simplificadas ? 'translate-x-4' : ''" />
            </div>
            <span class="text-xs text-slate-600 dark:text-slate-300">Apenas Easy Apply</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <div class="relative">
              <input type="checkbox" v-model="configReuso.candidatura_simplificada" class="sr-only" />
              <div class="w-8 h-4 rounded-full transition-colors" :class="configReuso.candidatura_simplificada ? 'bg-violet-600' : 'bg-slate-300 dark:bg-slate-600'" />
              <div class="absolute top-0 left-0 w-4 h-4 rounded-full bg-white shadow transition-transform" :class="configReuso.candidatura_simplificada ? 'translate-x-4' : ''" />
            </div>
            <span class="text-xs text-slate-600 dark:text-slate-300">Texto simplificado</span>
          </label>
        </div>

        <p v-if="erroReuso" class="text-xs text-red-600 dark:text-red-400 mb-2">{{ erroReuso }}</p>

        <button
          :disabled="iniciandoReuso"
          @click="iniciarReuso"
          class="w-full py-2 rounded-lg text-sm font-semibold transition-colors"
          :class="iniciandoReuso ? 'bg-slate-200 text-slate-400 dark:bg-slate-800 cursor-not-allowed' : 'bg-indigo-600 text-white hover:bg-indigo-700'"
        >
          {{ iniciandoReuso ? 'Iniciando...' : 'Iniciar novo pipeline' }}
        </button>
      </div>
    </div>

    <!-- Upload + Config -->
    <div class="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
      <h2 class="text-base font-semibold text-slate-700 dark:text-slate-200 mb-4">Novo pipeline</h2>

      <div
        class="border-2 border-dashed rounded-xl flex flex-col items-center justify-center gap-3 py-10 cursor-pointer transition-colors"
        :class="
          dragOver
            ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-950/30'
            : 'border-slate-300 dark:border-slate-600 hover:border-indigo-400'
        "
        @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false"
        @drop.prevent="onDrop"
        @click="($refs.fileInput as HTMLInputElement).click()"
      >
        <span class="text-4xl">📄</span>
        <div class="text-center">
          <p class="text-sm font-medium text-slate-700 dark:text-slate-300">
            {{ cvFile ? cvFile.name : 'Arraste o PDF ou clique para selecionar' }}
          </p>
          <p class="text-xs text-slate-400 mt-0.5">Somente PDF · máx. 10 MB</p>
        </div>
        <input ref="fileInput" type="file" accept=".pdf" class="hidden" @change="onFileInput" />
      </div>

      <button
        @click="mostrarConfig = !mostrarConfig"
        class="mt-4 flex items-center gap-1.5 text-xs font-medium text-indigo-500 hover:text-indigo-700"
      >
        <svg class="w-3.5 h-3.5 transition-transform" :class="mostrarConfig ? 'rotate-180' : ''" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
        Configurações avançadas
      </button>

      <div v-if="mostrarConfig" class="mt-4 rounded-xl border border-slate-200 dark:border-slate-700 p-4 space-y-4">
        <!-- Fontes -->
        <div>
          <p class="text-xs font-semibold text-slate-600 dark:text-slate-300 mb-2">Origens de busca</p>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="fonte in FONTES_DISPONIVEIS"
              :key="fonte"
              @click="toggleFonte(fonte)"
              class="px-3 py-1.5 rounded-full text-xs font-medium border transition-colors"
              :class="
                config.fontes.includes(fonte)
                  ? 'bg-indigo-600 text-white border-indigo-600'
                  : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-300 dark:border-slate-600 hover:border-indigo-400'
              "
            >
              {{ FONTE_LABELS[fonte] }}
            </button>
          </div>
        </div>

        <!-- Quantidades -->
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="text-xs font-semibold text-slate-600 dark:text-slate-300 block mb-1">
              Máx. vagas por fonte <span class="font-normal text-slate-400">(1-50)</span>
            </label>
            <input
              v-model.number="config.max_vagas_por_fonte"
              type="number" min="1" max="50"
              class="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-sm text-slate-700 dark:text-slate-200 px-3 py-1.5"
            />
          </div>
          <div>
            <label class="text-xs font-semibold text-slate-600 dark:text-slate-300 block mb-1">
              Máx. candidaturas geradas <span class="font-normal text-slate-400">(1-20)</span>
            </label>
            <input
              v-model.number="config.max_personalizar"
              type="number" min="1" max="20"
              class="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-sm text-slate-700 dark:text-slate-200 px-3 py-1.5"
            />
          </div>
        </div>

        <!-- Apenas simplificadas -->
        <label class="flex items-start gap-3 cursor-pointer">
          <div class="relative mt-0.5">
            <input type="checkbox" v-model="config.apenas_simplificadas" class="sr-only" />
            <div class="w-9 h-5 rounded-full transition-colors" :class="config.apenas_simplificadas ? 'bg-indigo-600' : 'bg-slate-300 dark:bg-slate-600'" />
            <div class="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform" :class="config.apenas_simplificadas ? 'translate-x-4' : ''" />
          </div>
          <div>
            <p class="text-xs font-semibold text-slate-700 dark:text-slate-200">Apenas candidatura simplificada</p>
            <p class="text-xs text-slate-400 mt-0.5">
              Filtra apenas vagas com Easy Apply, Gupy Apply ou candidatura direta na plataforma.
            </p>
          </div>
        </label>

        <!-- Texto simplificado -->
        <label class="flex items-start gap-3 cursor-pointer">
          <div class="relative mt-0.5">
            <input type="checkbox" v-model="config.candidatura_simplificada" class="sr-only" />
            <div class="w-9 h-5 rounded-full transition-colors" :class="config.candidatura_simplificada ? 'bg-violet-600' : 'bg-slate-300 dark:bg-slate-600'" />
            <div class="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform" :class="config.candidatura_simplificada ? 'translate-x-4' : ''" />
          </div>
          <div>
            <p class="text-xs font-semibold text-slate-700 dark:text-slate-200">Texto simplificado</p>
            <p class="text-xs text-slate-400 mt-0.5">
              Gera resumo de 1 parágrafo e carta de 3 frases — ideal para formulários com limite de caracteres.
            </p>
          </div>
        </label>
      </div>

      <p v-if="erro" class="mt-3 text-sm text-red-600 dark:text-red-400">{{ erro }}</p>

      <button
        :disabled="!cvFile || enviando"
        @click="iniciarPipeline"
        class="mt-4 w-full py-2.5 rounded-lg text-sm font-semibold transition-colors"
        :class="!cvFile || enviando ? 'bg-slate-200 text-slate-400 cursor-not-allowed dark:bg-slate-800 dark:text-slate-600' : 'bg-indigo-600 text-white hover:bg-indigo-700'"
      >
        <span v-if="enviando">Iniciando...</span>
        <span v-else>Iniciar pipeline</span>
      </button>
    </div>

    <!-- Histórico -->
    <div class="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700">
      <div class="px-6 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <h2 class="text-base font-semibold text-slate-700 dark:text-slate-200">Histórico</h2>
          <span v-if="candidatoFiltro !== null" class="text-xs bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400 px-2 py-0.5 rounded-full">
            filtrado
          </span>
        </div>
        <button @click="carregar" class="text-xs text-indigo-500 hover:text-indigo-700">Atualizar</button>
      </div>

      <div v-if="carregando" class="p-8 text-center text-slate-400 text-sm">Carregando...</div>
      <div v-else-if="pipelinesFiltrados.length === 0" class="p-8 text-center text-slate-400 text-sm">
        {{ candidatoFiltro !== null ? 'Nenhum pipeline para este perfil ainda.' : 'Nenhum pipeline ainda. Envie seu currículo acima.' }}
      </div>

      <ul v-else class="divide-y divide-slate-100 dark:divide-slate-800">
        <li
          v-for="run in pipelinesFiltrados"
          :key="run.id"
          class="flex items-center justify-between px-6 py-4 hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer"
          @click="router.push({ name: 'pipeline-detalhe', params: { id: run.id } })"
        >
          <div class="flex items-center gap-3">
            <!-- Avatar do candidato associado -->
            <div
              v-if="candidatos.find(c => c.id === run.candidato_id)"
              class="w-7 h-7 rounded-full bg-indigo-500 flex items-center justify-center text-xs font-bold text-white shrink-0"
              :title="candidatos.find(c => c.id === run.candidato_id)?.nome"
            >
              {{ iniciais(candidatos.find(c => c.id === run.candidato_id)?.nome || 'C') }}
            </div>
            <div class="flex flex-col gap-0.5">
              <span class="text-sm font-medium text-slate-700 dark:text-slate-200">Pipeline #{{ run.id }}</span>
              <span class="text-xs text-slate-400">{{ formatData(run.created_at) }}</span>
            </div>
          </div>

          <div class="flex items-center gap-4">
            <div v-if="run.status === 'CONCLUIDO'" class="text-xs text-slate-500 dark:text-slate-400 text-right">
              <span>{{ run.vagas_encontradas }} vagas</span>
              <span class="mx-1">·</span>
              <span>{{ run.candidaturas_criadas }} candidaturas</span>
            </div>
            <span class="text-xs font-medium px-2.5 py-1 rounded-full" :class="statusClass(run.status)">
              {{ statusLabel(run.status) }}
            </span>
            <svg class="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>
