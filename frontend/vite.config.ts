import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: true,
    proxy: {
      '/api': { target: 'http://api:8000', changeOrigin: true },
      '/auth': { target: 'http://api:8000', changeOrigin: true },
      '/agents': { target: 'http://api:8000', changeOrigin: true },
      '/health': { target: 'http://api:8000', changeOrigin: true },
      '/documents': { target: 'http://api:8000', changeOrigin: true },
      '/session': { target: 'http://api:8000', changeOrigin: true },
      // /chat proxied ao backend; bypass devolve index.html para navegacao direta
      '/chat': {
        target: 'http://api:8000',
        changeOrigin: true,
        bypass(req) {
          if (req.headers.accept?.includes('text/html')) return '/index.html'
        },
      },
    },
  },
})
