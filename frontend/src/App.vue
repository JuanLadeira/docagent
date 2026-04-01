<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, RouterLink, RouterView } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useApiStatusStore } from '@/stores/apiStatus'
import { useThemeStore, type ThemeMode } from '@/stores/theme'

const route = useRoute()
const auth = useAuthStore()
const apiStatus = useApiStatusStore()
const themeStore = useThemeStore()

onMounted(() => themeStore.init())

const isAdminRoute = computed(() => route.path.startsWith('/sys-mgmt'))
const isPublicRoute = computed(() =>
  ['/login', '/forgot-password', '/reset-password'].includes(route.path),
)
const showSidebar = computed(() => !isAdminRoute.value && !isPublicRoute.value && auth.isAuthenticated)

const navItems = computed(() => {
  const items = [
    { name: 'Conversa', path: '/conversa', icon: '💬' },
  ]
  if (auth.isOwner) {
    items.push({ name: 'Atendimentos WA', path: '/atendimentos', icon: '📱' })
    items.push({ name: 'Atendimentos TG', path: '/atendimentos/telegram', icon: '✈️' })
    items.push({ name: 'Contatos', path: '/contatos', icon: '👤' })
    items.push({ name: 'Agentes', path: '/agentes', icon: '🤖' })
    items.push({ name: 'Servidores MCP', path: '/servidores-mcp', icon: '🔌' })
  }
  items.push({ name: 'Configurações', path: '/configuracoes', icon: '⚙️' })
  return items
})

const themeOptions: { value: ThemeMode; label: string; icon: string }[] = [
  { value: 'light', label: 'Claro', icon: '☀️' },
  { value: 'dark', label: 'Escuro', icon: '🌙' },
  { value: 'system', label: 'Sistema', icon: '🖥️' },
]
</script>

<template>
  <!-- Banner: API indisponível -->
  <div
    v-if="apiStatus.isDown"
    class="fixed top-0 inset-x-0 z-[9999] flex items-center justify-center gap-3 bg-amber-500 text-white text-sm font-medium py-2.5 px-4"
  >
    <svg class="animate-spin w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24">
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
    </svg>
    API indisponível — reconectando em 5s...
  </div>

  <!-- Admin: layout próprio em AdminLayoutView -->
  <RouterView v-if="isAdminRoute" />

  <!-- Público: sem sidebar -->
  <RouterView v-else-if="isPublicRoute" />

  <!-- Autenticado: sidebar + conteúdo -->
  <div v-else class="flex h-screen overflow-hidden bg-gray-50 dark:bg-slate-950">
    <!-- Sidebar -->
    <aside
      v-if="showSidebar"
      class="w-56 flex-shrink-0 flex flex-col border-r border-slate-700"
      style="background: #0f172a"
    >
      <!-- Logo -->
      <div class="p-5 border-b border-slate-700">
        <div class="flex items-center gap-2">
          <span class="text-2xl">📄</span>
          <div>
            <div class="text-white font-bold text-sm">z3ndocs</div>
            <div class="text-slate-400 text-xs">AI Document Assistant</div>
          </div>
        </div>
      </div>

      <!-- Nav -->
      <nav class="flex-1 p-3 space-y-1 overflow-y-auto">
        <RouterLink
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors"
          :class="
            route.path === item.path || route.path.startsWith(item.path + '/')
              ? 'bg-indigo-600 text-white'
              : 'text-slate-400 hover:text-white hover:bg-slate-700'
          "
        >
          <span>{{ item.icon }}</span>
          <span>{{ item.name }}</span>
        </RouterLink>
      </nav>

      <!-- Theme toggle -->
      <div class="px-3 py-3 border-t border-slate-700">
        <div class="flex items-center gap-1 bg-slate-800 rounded-lg p-1">
          <button
            v-for="opt in themeOptions"
            :key="opt.value"
            :title="opt.label"
            @click="themeStore.setTheme(opt.value)"
            class="flex-1 flex items-center justify-center py-1 rounded text-xs transition-colors"
            :class="
              themeStore.theme === opt.value
                ? 'bg-slate-600 text-white'
                : 'text-slate-500 hover:text-slate-300'
            "
          >
            {{ opt.icon }}
          </button>
        </div>
      </div>

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
      <RouterView :key="route.path" />
    </main>
  </div>
</template>
