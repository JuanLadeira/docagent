<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const erro = ref('')

onMounted(async () => {
  const token = route.query.token as string | undefined
  if (!token) {
    erro.value = 'Token não encontrado na URL.'
    return
  }
  try {
    await auth.setTokenFromKeycloak(token)
    router.replace('/conversa')
  } catch {
    erro.value = 'Erro ao autenticar com Keycloak. Tente novamente.'
  }
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-slate-900">
    <div class="text-center">
      <div v-if="!erro" class="text-slate-400 text-sm">Autenticando via Keycloak...</div>
      <div v-else class="text-red-400 text-sm">{{ erro }}</div>
    </div>
  </div>
</template>
