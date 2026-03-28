import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, type Agente } from '@/api/client'

export const useAgentsStore = defineStore('agents', () => {
  const agents = ref<Agente[]>([])
  const isFetching = ref(false)
  const fetched = ref(false)

  async function fetchIfNeeded() {
    if (fetched.value || isFetching.value) return
    isFetching.value = true
    try {
      const res = await api.listAgentes()
      agents.value = res.data
      fetched.value = true
    } catch {
      agents.value = []
    } finally {
      isFetching.value = false
    }
  }

  function invalidate() {
    fetched.value = false
    agents.value = []
  }

  return { agents, isFetching, fetchIfNeeded, invalidate }
})
