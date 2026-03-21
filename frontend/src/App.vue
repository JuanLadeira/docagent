<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, RouterView } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const auth = useAuthStore()

const isAdminRoute = computed(() => route.path.startsWith('/sys-mgmt'))
const isPublicRoute = computed(() =>
  ['/login', '/forgot-password', '/reset-password'].includes(route.path),
)
const showSidebar = computed(() => !isAdminRoute.value && !isPublicRoute.value && auth.isAuthenticated)

const navItems = [
  { name: 'Conversa', path: '/conversa', icon: '💬' },
  { name: 'Configurações', path: '/configuracoes', icon: '⚙️' },
]
</script>

<template>
  <!-- Admin: layout proprio em AdminLayoutView -->
  <RouterView v-if="isAdminRoute" />

  <!-- Publico: sem sidebar -->
  <RouterView v-else-if="isPublicRoute" />

  <!-- Autenticado: sidebar + conteudo -->
  <div v-else class="flex h-screen overflow-hidden bg-gray-50">
    <!-- Sidebar -->
    <aside
      v-if="showSidebar"
      class="w-56 flex-shrink-0 flex flex-col"
      style="background: #0f172a"
    >
      <!-- Logo -->
      <div class="p-5 border-b border-slate-700">
        <div class="flex items-center gap-2">
          <span class="text-2xl">📄</span>
          <div>
            <div class="text-white font-bold text-sm">DocAgent</div>
            <div class="text-slate-400 text-xs">AI Document Assistant</div>
          </div>
        </div>
      </div>

      <!-- Nav -->
      <nav class="flex-1 p-3 space-y-1">
        <RouterLink
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors"
          :class="
            route.path === item.path
              ? 'bg-indigo-600 text-white'
              : 'text-slate-400 hover:text-white hover:bg-slate-700'
          "
        >
          <span>{{ item.icon }}</span>
          <span>{{ item.name }}</span>
        </RouterLink>
      </nav>

      <!-- User -->
      <div class="p-3 border-t border-slate-700">
        <div class="flex items-center gap-3 px-2 py-2">
          <div
            class="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
            style="background: linear-gradient(135deg, #6366f1, #8b5cf6)"
          >
            {{ (auth.username ?? 'U')[0].toUpperCase() }}
          </div>
          <div class="flex-1 min-w-0">
            <div class="text-white text-xs font-medium truncate">{{ auth.username }}</div>
            <div class="text-slate-400 text-xs">{{ auth.role }}</div>
          </div>
        </div>
        <button
          @click="auth.logout()"
          class="w-full mt-1 text-left px-3 py-2 text-xs text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
        >
          Sair
        </button>
      </div>
    </aside>

    <!-- Main -->
    <main class="flex-1 overflow-hidden">
      <RouterView />
    </main>
  </div>
</template>
