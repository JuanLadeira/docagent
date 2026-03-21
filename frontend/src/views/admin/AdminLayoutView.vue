<script setup lang="ts">
import { RouterView, RouterLink, useRoute } from 'vue-router'
import { useAdminAuthStore } from '@/stores/adminAuth'

const adminAuth = useAdminAuthStore()
const route = useRoute()

const navItems = [
  { path: '/sys-mgmt/tenants', label: 'Tenants', icon: '🏢' },
  { path: '/sys-mgmt/planos', label: 'Planos', icon: '📋' },
  { path: '/sys-mgmt/assinaturas', label: 'Assinaturas', icon: '📄' },
]
</script>

<template>
  <div class="flex h-screen overflow-hidden" style="background: #0f172a">
    <!-- Sidebar admin -->
    <aside class="w-56 flex-shrink-0 flex flex-col border-r border-slate-700">
      <div class="p-5 border-b border-slate-700">
        <div class="text-white font-bold text-sm">DocAgent Admin</div>
        <div class="text-slate-400 text-xs mt-0.5">{{ adminAuth.username }}</div>
      </div>

      <nav class="flex-1 p-3 space-y-1">
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

      <div class="p-3 border-t border-slate-700">
        <button
          @click="adminAuth.logout()"
          class="w-full text-left px-3 py-2 text-xs text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
        >
          Sair
        </button>
      </div>
    </aside>

    <!-- Conteudo -->
    <main class="flex-1 bg-gray-50 overflow-y-auto">
      <RouterView />
    </main>
  </div>
</template>
