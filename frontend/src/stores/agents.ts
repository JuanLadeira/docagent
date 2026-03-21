import { defineStore } from 'pinia'
import { ref } from 'vue'
import { docagentApi, type Agent } from '@/api/docagent'

export const useAgentsStore = defineStore('agents', () => {
  const agents = ref<Agent[]>([])
  const isFetching = ref(false)
  const fetched = ref(false)

  async function fetchIfNeeded() {
    if (fetched.value || isFetching.value) return
    isFetching.value = true
    try {
      const res = await docagentApi.getAgents()
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
