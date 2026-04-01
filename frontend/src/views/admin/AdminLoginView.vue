<script setup lang="ts">
import { ref } from 'vue'
import { useAdminAuthStore } from '@/stores/adminAuth'

const adminAuth = useAdminAuthStore()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleSubmit() {
  loading.value = true
  error.value = ''
  const result = await adminAuth.login(username.value, password.value)
  if (!result.success) error.value = result.error ?? 'Erro ao fazer login'
  loading.value = false
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center" style="background: #0f172a">
    <div class="w-full max-w-md px-6">
      <div class="text-center mb-8">
        <div class="text-5xl mb-3">🛡️</div>
        <h1 class="text-white text-2xl font-bold">z3ndocs Admin</h1>
        <p class="text-slate-400 text-sm mt-1">Painel de administração</p>
      </div>

      <div class="bg-slate-800 rounded-2xl p-8 shadow-xl">
        <form @submit.prevent="handleSubmit" class="space-y-4">
          <div>
            <label class="block text-slate-400 text-sm mb-1">Usuário</label>
            <input
              v-model="username"
              type="text"
              required
              class="w-full bg-slate-700 text-white rounded-lg px-4 py-3 text-sm placeholder-slate-500 outline-none focus:ring-2 focus:ring-violet-500"
            />
          </div>
          <div>
            <label class="block text-slate-400 text-sm mb-1">Senha</label>
            <input
              v-model="password"
              type="password"
              required
              class="w-full bg-slate-700 text-white rounded-lg px-4 py-3 text-sm placeholder-slate-500 outline-none focus:ring-2 focus:ring-violet-500"
            />
          </div>

          <div v-if="error" class="bg-red-900/40 border border-red-700 text-red-300 text-sm rounded-lg px-4 py-3">
            {{ error }}
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="w-full bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white font-medium rounded-lg py-3 text-sm transition-colors"
          >
            {{ loading ? 'Entrando...' : 'Entrar como Admin' }}
          </button>
        </form>
      </div>

      <p class="text-slate-600 text-xs text-center mt-6">
        <RouterLink to="/login" class="text-slate-500 hover:text-slate-400">
          ← Acesso de usuário
        </RouterLink>
      </p>
    </div>
  </div>
</template>
