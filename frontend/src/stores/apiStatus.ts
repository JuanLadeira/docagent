import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

export const useApiStatusStore = defineStore('apiStatus', () => {
  const isDown = ref(false)
  let pollingTimer: ReturnType<typeof setTimeout> | null = null

  function startPolling() {
    if (pollingTimer !== null) return
    poll()
  }

  function poll() {
    pollingTimer = setTimeout(async () => {
      try {
        await axios.get('/api/health', { timeout: 4000 })
        isDown.value = false
        pollingTimer = null
      } catch {
        poll()
      }
    }, 5000)
  }

  function reportDown() {
    if (!isDown.value) {
      isDown.value = true
      startPolling()
    }
  }

  return { isDown, reportDown }
})
