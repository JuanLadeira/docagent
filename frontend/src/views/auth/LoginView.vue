<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleSubmit() {
  if (!username.value || !password.value) return
  loading.value = true
  error.value = ''
  const result = await auth.login(username.value, password.value)
  if (!result.success) error.value = result.error ?? 'Erro ao fazer login'
  loading.value = false
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-slate-900">
    <div class="w-full max-w-md px-6">
      <!-- Logo -->
      <div class="text-center mb-8">
        <div class="text-5xl mb-3">📄</div>
        <h1 class="text-white text-2xl font-bold">DocAgent</h1>
        <p class="text-slate-400 text-sm mt-1">AI Document Assistant</p>
      </div>

      <!-- Card -->
      <div class="bg-slate-800 rounded-2xl p-8 shadow-xl">
        <h2 class="text-white text-lg font-semibold mb-6">Entrar na sua conta</h2>

        <form @submit.prevent="handleSubmit" class="space-y-4">
          <div>
            <label class="block text-slate-400 text-sm mb-1">Usuário</label>
            <input
              v-model="username"
              type="text"
              placeholder="seu.usuario"
              required
              class="w-full bg-slate-700 text-white rounded-lg px-4 py-3 text-sm placeholder-slate-500 outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label class="block text-slate-400 text-sm mb-1">Senha</label>
            <input
              v-model="password"
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
            {{ loading ? 'Entrando...' : 'Entrar' }}
          </button>
        </form>

        <div class="mt-4 text-center">
          <RouterLink to="/forgot-password" class="text-indigo-400 hover:text-indigo-300 text-sm">
            Esqueceu a senha?
          </RouterLink>
        </div>
      </div>

      <p class="text-slate-600 text-xs text-center mt-6">
        Admin?
        <RouterLink to="/sys-mgmt/login" class="text-slate-500 hover:text-slate-400">
          Acesso administrativo
        </RouterLink>
      </p>
    </div>
  </div>
</template>
