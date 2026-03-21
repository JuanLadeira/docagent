<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'

const route = useRoute()
const router = useRouter()
const newPassword = ref('')
const confirm = ref('')
const loading = ref(false)
const error = ref('')
const success = ref(false)

async function handleSubmit() {
  if (newPassword.value !== confirm.value) {
    error.value = 'As senhas não coincidem'
    return
  }
  const token = route.query.token as string
  if (!token) {
    error.value = 'Token inválido'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await api.resetPassword(token, newPassword.value)
    success.value = true
    setTimeout(() => router.push('/login'), 2000)
  } catch {
    error.value = 'Token inválido ou expirado'
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
        <h2 class="text-white text-lg font-semibold mb-4">Nova senha</h2>

        <div v-if="success" class="bg-green-900/40 border border-green-700 text-green-300 text-sm rounded-lg px-4 py-4">
          Senha redefinida com sucesso! Redirecionando...
        </div>

        <form v-else @submit.prevent="handleSubmit" class="space-y-4">
          <div>
            <label class="block text-slate-400 text-sm mb-1">Nova senha</label>
            <input
              v-model="newPassword"
              type="password"
              placeholder="••••••••"
              required
              class="w-full bg-slate-700 text-white rounded-lg px-4 py-3 text-sm placeholder-slate-500 outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label class="block text-slate-400 text-sm mb-1">Confirmar senha</label>
            <input
              v-model="confirm"
              type="password"
              placeholder="••••••••"
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
            {{ loading ? 'Salvando...' : 'Redefinir senha' }}
          </button>
        </form>
      </div>
    </div>
  </div>
</template>
