import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ThemeMode = 'light' | 'dark' | 'system'

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<ThemeMode>((localStorage.getItem('theme') as ThemeMode) ?? 'system')
  let mq: MediaQueryList | null = null

  function applyTheme() {
    const isDark =
      theme.value === 'dark' ||
      (theme.value === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
    document.documentElement.classList.toggle('dark', isDark)
  }

  function setTheme(t: ThemeMode) {
    theme.value = t
    localStorage.setItem('theme', t)
    applyTheme()
    setupListener()
  }

  function setupListener() {
    if (mq) mq.removeEventListener('change', applyTheme)
    mq = null
    if (theme.value === 'system') {
      mq = window.matchMedia('(prefers-color-scheme: dark)')
      mq.addEventListener('change', applyTheme)
    }
  }

  function init() {
    applyTheme()
    setupListener()
  }

  return { theme, setTheme, init }
})
