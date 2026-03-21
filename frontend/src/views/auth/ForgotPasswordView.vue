<script setup lang="ts">
import { ref } from 'vue'
import { api } from '@/api/client'

const email = ref('')
const loading = ref(false)
const sent = ref(false)
const error = ref('')

async function handleSubmit() {
  loading.value = true
  error.value = ''
  try {
    await api.forgotPassword(email.value)
    sent.value = true
  } catch {
    error.value = 'Erro ao processar solicitação. Tente novamente.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-slate-900">
    <div class="w-full max-w-md px-6">
      <div class="text-center mb-8">
        <div class="text-5xl mb-3">📄</div>
        <h1 class="text-white text-2xl font-bold">DocAgent</h1>
      </div>

      <div class="bg-slate-800 rounded-2xl p-8 shadow-xl">
        <h2 class="text-white text-lg font-semibold mb-2">Recuperar senha</h2>

        <div v-if="sent" class="bg-green-900/40 border border-green-700 text-green-300 text-sm rounded-lg px-4 py-4">
          Se o e-mail existir, você receberá um link de recuperação em breve.
        </div>

        <form v-else @submit.prevent="handleSubmit" class="space-y-4 mt-4">
          <div>
            <label class="block text-slate-400 text-sm mb-1">E-mail</label>
            <input
              v-model="email"
              type="email"
              placeholder="voce@exemplo.com"
              required
              class="w-full bg-slate-700 text-white rounded-lg px-4 py-3 text-sm placeholder-slate-500 outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div v-if="error" class="bg-red-900/40 border border-red-700 text-red-300 text-sm rounded-lg px-4 py-3">
            {{ error }}
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium rounded-lg py-3 text-sm transition-colors"
          >
            {{ loading ? 'Enviando...' : 'Enviar link de recuperação' }}
          </button>
        </form>

        <div class="mt-4 text-center">
          <RouterLink to="/login" class="text-indigo-400 hover:text-indigo-300 text-sm">
            ← Voltar ao login
          </RouterLink>
        </div>
      </div>
    </div>
  </div>
</template>
