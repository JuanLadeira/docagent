<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/api/client'
import WhatsappView from '@/views/whatsapp/WhatsappView.vue'
import TelegramView from '@/views/telegram/TelegramView.vue'
import McpServidoresView from '@/views/McpServidoresView.vue'

type SettingsTab = 'perfil' | 'whatsapp' | 'telegram' | 'mcp'

const auth = useAuthStore()
const abaAtiva = ref<SettingsTab>('perfil')

const tabs: { key: SettingsTab; label: string; icon: string; ownerOnly: boolean }[] = [
  { key: 'perfil', label: 'Perfil', icon: '👤', ownerOnly: false },
  { key: 'whatsapp', label: 'WhatsApp', icon: '📱', ownerOnly: true },
  { key: 'telegram', label: 'Telegram', icon: '✈️', ownerOnly: true },
  { key: 'mcp', label: 'Servidores MCP', icon: '🔌', ownerOnly: true },
]

const currentPassword = ref('')
const newPassword = ref('')
const confirm = ref('')
const loading = ref(false)
const success = ref(false)
const error = ref('')

async function changePassword() {
  if (newPassword.value !== confirm.value) {
    error.value = 'As senhas não coincidem'
    return
  }
  loading.value = true
  error.value = ''
  success.value = false
  try {
    await api.changePassword(currentPassword.value, newPassword.value)
    success.value = true
    currentPassword.value = ''
    newPassword.value = ''
    confirm.value = ''
  } catch {
    error.value = 'Senha atual incorreta'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="h-full overflow-y-auto" style="background: #f8fafc">
    <!-- Tab bar -->
    <div class="border-b border-slate-200 bg-white px-8">
      <div class="flex gap-1">
        <button
          v-for="tab in tabs.filter(t => !t.ownerOnly || auth.isOwner)"
          :key="tab.key"
          @click="abaAtiva = tab.key"
          class="flex items-center gap-1.5 px-4 py-4 text-sm font-medium border-b-2 transition-colors"
          :class="
            abaAtiva === tab.key
              ? 'border-indigo-500 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          "
        >
          <span>{{ tab.icon }}</span>
          <span>{{ tab.label }}</span>
        </button>
      </div>
    </div>

    <!-- Aba: Perfil -->
    <div v-show="abaAtiva === 'perfil'" class="p-8 max-w-lg">
      <!-- Perfil -->
      <div class="bg-white rounded-xl border border-slate-200 p-6 mb-6">
        <h2 class="text-slate-700 font-semibold mb-4">Perfil</h2>
        <div class="space-y-3 text-sm">
          <div class="flex gap-4">
            <span class="text-slate-400 w-24">Usuário</span>
            <span class="text-slate-700 font-medium">{{ auth.username }}</span>
          </div>
          <div class="flex gap-4">
            <span class="text-slate-400 w-24">Perfil</span>
            <span
              class="px-2 py-0.5 rounded text-xs font-medium"
              :class="auth.isOwner ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100 text-slate-600'"
            >
              {{ auth.role }}
            </span>
          </div>
          <div class="flex gap-4">
            <span class="text-slate-400 w-24">Tenant ID</span>
            <span class="text-slate-700">{{ auth.tenantId }}</span>
          </div>
        </div>
      </div>

      <!-- Alterar senha -->
      <div class="bg-white rounded-xl border border-slate-200 p-6">
        <h2 class="text-slate-700 font-semibold mb-4">Alterar senha</h2>

        <div
          v-if="success"
          class="bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg px-4 py-3 mb-4"
        >
          Senha alterada com sucesso!
        </div>

        <form @submit.prevent="changePassword" class="space-y-3">
          <div>
            <label class="block text-slate-500 text-sm mb-1">Senha atual</label>
            <input
              v-model="currentPassword"
              type="password"
              required
              class="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>
          <div>
            <label class="block text-slate-500 text-sm mb-1">Nova senha</label>
            <input
              v-model="newPassword"
              type="password"
              required
              class="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>
          <div>
            <label class="block text-slate-500 text-sm mb-1">Confirmar nova senha</label>
            <input
              v-model="confirm"
              type="password"
              required
              class="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>

          <div v-if="error" class="text-red-500 text-sm">{{ error }}</div>

          <button
            type="submit"
            :disabled="loading"
            class="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium rounded-lg py-2.5 text-sm transition-colors"
          >
            {{ loading ? 'Salvando...' : 'Alterar senha' }}
          </button>
        </form>
      </div>
    </div>

    <!-- Aba: WhatsApp -->
    <WhatsappView v-show="abaAtiva === 'whatsapp'" />

    <!-- Aba: Telegram -->
    <TelegramView v-show="abaAtiva === 'telegram'" />

    <!-- Aba: Servidores MCP -->
    <McpServidoresView v-show="abaAtiva === 'mcp'" />
  </div>
</template>
