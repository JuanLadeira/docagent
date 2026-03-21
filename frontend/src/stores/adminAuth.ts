import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import router from '@/router'

export const useAdminAuthStore = defineStore('adminAuth', () => {
  const token = ref<string | null>(localStorage.getItem('admin_token'))
  const username = ref<string | null>(localStorage.getItem('admin_username'))

  const isAuthenticated = computed(() => !!token.value)

  async function login(usernameInput: string, password: string) {
    try {
      const response = await axios.post<{ access_token: string }>(
        '/api/admin/login',
        new URLSearchParams({ username: usernameInput, password }),
      )
      token.value = response.data.access_token
      username.value = usernameInput
      localStorage.setItem('admin_token', response.data.access_token)
      localStorage.setItem('admin_username', usernameInput)
      router.push('/sys-mgmt')
      return { success: true }
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      return {
        success: false,
        error: err.response?.data?.detail ?? 'Erro ao fazer login',
      }
    }
  }

  function logout() {
    token.value = null
    username.value = null
    localStorage.removeItem('admin_token')
    localStorage.removeItem('admin_username')
    router.push('/sys-mgmt/login')
  }

  return { token, username, isAuthenticated, login, logout }
})
