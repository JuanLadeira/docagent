<script setup lang="ts">
import { RouterView, RouterLink, useRoute } from 'vue-router'
import { useAdminAuthStore } from '@/stores/adminAuth'
import { useThemeStore, type ThemeMode } from '@/stores/theme'

const adminAuth = useAdminAuthStore()
const themeStore = useThemeStore()
const route = useRoute()

const navItems = [
  { path: '/sys-mgmt/tenants',       label: 'Tenants',       icon: '🏢' },
  { path: '/sys-mgmt/planos',        label: 'Planos',        icon: '📋' },
  { path: '/sys-mgmt/assinaturas',   label: 'Assinaturas',   icon: '📄' },
  { path: '/sys-mgmt/configuracoes', label: 'Configurações', icon: '⚙️' },
]

const themeOptions: { value: ThemeMode; label: string; icon: string }[] = [
  { value: 'light',  label: 'Claro',   icon: '☀️' },
  { value: 'dark',   label: 'Escuro',  icon: '🌙' },
  { value: 'system', label: 'Sistema', icon: '🖥️' },
]
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-gray-50 dark:bg-slate-950">
    <!-- Sidebar -->
    <aside class="w-56 flex-shrink-0 flex flex-col border-r border-slate-700" style="background: #0f172a">
      <!-- Logo -->
      <div class="p-5 border-b border-slate-700">
        <div class="flex items-center gap-2">
          <span class="text-2xl">🛡️</span>
          <div>
            <div class="text-white font-bold text-sm">z3ndocs</div>
            <div class="text-violet-400 text-xs">Painel Admin</div>
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
            route.path === item.path
              ? 'bg-violet-600 text-white'
              : 'text-slate-400 hover:text-white hover:bg-slate-700'
          "
        >
          <span>{{ item.icon }}</span>
          <span>{{ item.label }}</span>
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
            style="background: linear-gradient(135deg, #7c3aed, #a855f7)"
          >
            {{ (adminAuth.username ?? 'A')[0].toUpperCase() }}
          </div>
          <div class="flex-1 min-w-0">
            <div class="text-white text-xs font-medium truncate">{{ adminAuth.username }}</div>
            <div class="text-violet-400 text-xs">Admin</div>
          </div>
        </div>
        <button
          @click="adminAuth.logout()"
          class="w-full mt-1 text-left px-3 py-2 text-xs text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
        >
          Sair
        </button>
      </div>
    </aside>

    <!-- Conteúdo -->
    <main class="flex-1 overflow-y-auto">
      <RouterView />
    </main>
  </div>
</template>
