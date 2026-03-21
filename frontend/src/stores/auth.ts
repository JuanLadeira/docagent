import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api/client'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(sessionStorage.getItem('token'))
  const username = ref<string | null>(sessionStorage.getItem('username'))
  const tenantId = ref<number | null>(
    sessionStorage.getItem('tenant_id') ? Number(sessionStorage.getItem('tenant_id')) : null,
  )
  const userId = ref<number | null>(
    sessionStorage.getItem('user_id') ? Number(sessionStorage.getItem('user_id')) : null,
  )
  const role = ref<'OWNER' | 'MEMBER' | null>(
    (sessionStorage.getItem('role') as 'OWNER' | 'MEMBER' | null) ?? null,
  )

  const isAuthenticated = computed(() => !!token.value)
  const isOwner = computed(() => role.value === 'OWNER')

  async function login(usernameInput: string, password: string) {
    try {
      const response = await api.login(usernameInput, password)
      token.value = response.data.access_token
      username.value = usernameInput
      sessionStorage.setItem('token', response.data.access_token)
      sessionStorage.setItem('username', usernameInput)

      const me = await api.getMe()
      tenantId.value = me.data.tenant_id
      userId.value = me.data.id
      role.value = me.data.role
      sessionStorage.setItem('tenant_id', String(me.data.tenant_id))
      sessionStorage.setItem('user_id', String(me.data.id))
      sessionStorage.setItem('role', me.data.role)

      router.push('/conversa')
      return { success: true }
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      return {
        success: false,
        error: err.response?.data?.detail ?? 'Usuário ou senha inválidos',
      }
    }
  }

  function logout() {
    token.value = null
    username.value = null
    tenantId.value = null
    userId.value = null
    role.value = null
    sessionStorage.clear()
    router.push('/login')
  }

  return { token, username, tenantId, userId, role, isAuthenticated, isOwner, login, logout }
})
