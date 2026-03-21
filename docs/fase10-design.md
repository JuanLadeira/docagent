# Fase 10 — Frontend Vue.js (Rewrite Completo)

## Objetivo

Substituir o Streamlit por um frontend Vue.js profissional, reescrito do zero.
O frontend é uma SPA completa com autenticação JWT, chat com streaming SSE,
admin panel para gestão de tenants/planos/assinaturas, e seleção de agentes.

Pré-requisitos: **Fases 8 e 9 concluídas** (API com auth, planos e assinaturas).

---

## Stack

| Camada | Tecnologia |
|---|---|
| Framework | Vue 3 + Composition API + `<script setup>` |
| Estado | Pinia |
| Roteamento | Vue Router 4 |
| HTTP | Axios |
| Estilo | Tailwind CSS v3 |
| Linguagem | TypeScript |
| Build | Vite |

Mesma arquitetura do frontend de referência em `/home/juan/projetos/rag/frontend/`.

---

## Estrutura de diretórios

```
docagent-frontend/
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
└── src/
    ├── main.ts
    ├── App.vue
    ├── api/
    │   ├── client.ts          ← Axios instance + interceptors
    │   ├── docagent.ts        ← /chat, /agents, /documents/upload
    │   └── auth.ts            ← /auth/login, /auth/forgot-password
    ├── stores/
    │   ├── auth.ts            ← token, userId, tenantId, role (sessionStorage)
    │   ├── adminAuth.ts       ← token admin separado
    │   ├── agents.ts          ← lista de agentes (cache)
    │   └── chat.ts            ← histórico, session_id, streaming state
    ├── router/
    │   └── index.ts           ← routes + beforeEach guard
    ├── views/
    │   ├── auth/
    │   │   ├── LoginView.vue
    │   │   ├── ForgotPasswordView.vue
    │   │   └── ResetPasswordView.vue
    │   ├── chat/
    │   │   └── ChatView.vue   ← interface principal
    │   ├── admin/
    │   │   ├── AdminLayout.vue
    │   │   ├── AdminLoginView.vue
    │   │   ├── AdminTenantsView.vue
    │   │   ├── AdminPlanosView.vue
    │   │   └── AdminAssinaturasView.vue
    │   └── user/
    │       └── SettingsView.vue
    └── components/
        ├── chat/
        │   ├── ChatMessage.vue      ← mensagem individual (markdown)
        │   ├── AgentSelector.vue    ← dropdown de agentes
        │   ├── FileUpload.vue       ← upload de PDF
        │   └── ChatInput.vue        ← textarea + send button
        └── shared/
            ├── AppSidebar.vue       ← sidebar de navegação
            └── LoadingSpinner.vue
```

---

## `api/client.ts`

```typescript
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
})

// Injeta Bearer token em todas as requests
apiClient.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

// Redireciona para /login em caso de 401
apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore().logout()
      router.push('/login')
    }
    return Promise.reject(error)
  }
)

export default apiClient
```

---

## `api/docagent.ts`

```typescript
import apiClient from './client'

export interface Agent {
  id: string
  name: string
  description: string
  skills: Skill[]
}

export interface Skill {
  name: string
  label: string
  icon: string
  description: string
}

export interface UploadResponse {
  filename: string
  chunks: number
  collection_id: string
}

export const docagentApi = {
  getAgents: (): Promise<Agent[]> =>
    apiClient.get('/agents').then(r => r.data),

  uploadDocument: (file: File, sessionId: string): Promise<UploadResponse> => {
    const form = new FormData()
    form.append('file', file)
    form.append('session_id', sessionId)
    return apiClient.post('/documents/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },

  // Streaming via fetch (não Axios — precisa de POST + ReadableStream)
  streamChat: (question: string, sessionId: string, agentId: string): ReadableStream => {
    return new ReadableStream({
      async start(controller) {
        const token = sessionStorage.getItem('token') ?? ''
        const res = await fetch(`${import.meta.env.VITE_API_URL}/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({ question, session_id: sessionId, agent_id: agentId }),
        })
        const reader = res.body!.getReader()
        const decoder = new TextDecoder()
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          controller.enqueue(decoder.decode(value))
        }
        controller.close()
      }
    })
  },
}
```

---

## `stores/auth.ts`

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(sessionStorage.getItem('token') ?? '')
  const userId = ref(sessionStorage.getItem('userId') ?? '')
  const tenantId = ref(sessionStorage.getItem('tenantId') ?? '')
  const role = ref(sessionStorage.getItem('role') ?? '')

  const isAuthenticated = computed(() => !!token.value)
  const isOwner = computed(() => role.value === 'OWNER')

  async function login(username: string, password: string) {
    const form = new URLSearchParams({ username, password })
    const { data } = await apiClient.post('/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    token.value = data.access_token
    sessionStorage.setItem('token', data.access_token)

    const me = await apiClient.get('/api/usuarios/me')
    userId.value = String(me.data.id)
    tenantId.value = String(me.data.tenant_id)
    role.value = me.data.role
    sessionStorage.setItem('userId', userId.value)
    sessionStorage.setItem('tenantId', tenantId.value)
    sessionStorage.setItem('role', role.value)
  }

  function logout() {
    token.value = ''
    userId.value = ''
    tenantId.value = ''
    role.value = ''
    sessionStorage.clear()
  }

  return { token, userId, tenantId, role, isAuthenticated, isOwner, login, logout }
})
```

---

## `stores/chat.ts`

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { v4 as uuidv4 } from 'uuid'

export interface Message {
  role: 'user' | 'assistant' | 'step'
  content: string
}

export const useChatStore = defineStore('chat', () => {
  const sessionId = ref(sessionStorage.getItem('chatSessionId') ?? uuidv4())
  const messages = ref<Message[]>([])
  const isLoading = ref(false)
  const selectedAgentId = ref('doc-analyst')

  sessionStorage.setItem('chatSessionId', sessionId.value)

  function addMessage(msg: Message) {
    messages.value.push(msg)
  }

  function resetSession() {
    sessionId.value = uuidv4()
    messages.value = []
    sessionStorage.setItem('chatSessionId', sessionId.value)
  }

  return { sessionId, messages, isLoading, selectedAgentId, addMessage, resetSession }
})
```

---

## `router/index.ts`

```typescript
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAdminAuthStore } from '@/stores/adminAuth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // Públicas
    { path: '/login', component: () => import('@/views/auth/LoginView.vue') },
    { path: '/forgot-password', component: () => import('@/views/auth/ForgotPasswordView.vue') },
    { path: '/reset-password', component: () => import('@/views/auth/ResetPasswordView.vue') },

    // Usuário autenticado
    {
      path: '/',
      redirect: '/chat',
      meta: { requiresAuth: true },
    },
    {
      path: '/chat',
      component: () => import('@/views/chat/ChatView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/settings',
      component: () => import('@/views/user/SettingsView.vue'),
      meta: { requiresAuth: true },
    },

    // Admin
    { path: '/sys-mgmt/login', component: () => import('@/views/admin/AdminLoginView.vue') },
    {
      path: '/sys-mgmt',
      component: () => import('@/views/admin/AdminLayout.vue'),
      meta: { requiresAdmin: true },
      children: [
        { path: 'tenants', component: () => import('@/views/admin/AdminTenantsView.vue') },
        { path: 'planos', component: () => import('@/views/admin/AdminPlanosView.vue') },
        { path: 'assinaturas', component: () => import('@/views/admin/AdminAssinaturasView.vue') },
      ],
    },
  ],
})

router.beforeEach((to, _from, next) => {
  const auth = useAuthStore()
  const adminAuth = useAdminAuthStore()

  if (to.meta.requiresAdmin && !adminAuth.isAuthenticated) {
    return next('/sys-mgmt/login')
  }
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return next('/login')
  }
  next()
})

export default router
```

---

## `views/chat/ChatView.vue` — estrutura

```vue
<template>
  <div class="flex h-screen">
    <!-- Sidebar -->
    <aside class="w-72 bg-gray-900 flex flex-col p-4 gap-4">
      <div class="text-white font-bold text-lg">DocAgent</div>

      <AgentSelector v-model="chatStore.selectedAgentId" />
      <FileUpload :session-id="chatStore.sessionId" />

      <button @click="chatStore.resetSession()" class="...">
        🗑️ Nova conversa
      </button>

      <div class="mt-auto text-gray-400 text-xs">
        Sessão: {{ chatStore.sessionId.slice(0, 8) }}...
      </div>
    </aside>

    <!-- Área de chat -->
    <main class="flex-1 flex flex-col">
      <div class="flex-1 overflow-y-auto p-6 space-y-4">
        <ChatMessage
          v-for="(msg, i) in chatStore.messages"
          :key="i"
          :message="msg"
        />
        <LoadingSpinner v-if="chatStore.isLoading" />
      </div>

      <ChatInput @send="handleSend" :disabled="chatStore.isLoading" />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useChatStore } from '@/stores/chat'
import { docagentApi } from '@/api/docagent'

const chatStore = useChatStore()

async function handleSend(question: string) {
  chatStore.addMessage({ role: 'user', content: question })
  chatStore.isLoading = true

  const stream = docagentApi.streamChat(
    question,
    chatStore.sessionId,
    chatStore.selectedAgentId,
  )
  const reader = stream.getReader()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += value
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      if (!line.startsWith('data:')) continue
      const event = JSON.parse(line.slice(5).trim())
      if (event.type === 'answer') {
        chatStore.addMessage({ role: 'assistant', content: event.content })
        chatStore.isLoading = false
      }
    }
  }
}
</script>
```

---

## `components/chat/AgentSelector.vue`

```vue
<script setup lang="ts">
import { onMounted } from 'vue'
import { useAgentsStore } from '@/stores/agents'

const agentsStore = useAgentsStore()
const modelValue = defineModel<string>()

onMounted(() => agentsStore.fetchIfNeeded())
</script>

<template>
  <div>
    <label class="text-gray-400 text-xs uppercase">Agente</label>
    <select v-model="modelValue" class="w-full bg-gray-800 text-white rounded p-2 mt-1">
      <option
        v-for="agent in agentsStore.agents"
        :key="agent.id"
        :value="agent.id"
      >
        {{ agent.name }}
      </option>
    </select>
  </div>
</template>
```

---

## Admin Panel — padrão de view

Todas as views admin seguem o mesmo padrão CRUD com tabela + modal:

```vue
<!-- AdminPlanosView.vue (estrutura representativa) -->
<template>
  <div>
    <div class="flex justify-between items-center mb-4">
      <h1>Planos</h1>
      <button @click="showModal = true">+ Novo Plano</button>
    </div>

    <table>
      <thead>...</thead>
      <tbody>
        <tr v-for="plano in planos" :key="plano.id">
          <td>{{ plano.nome }}</td>
          <td>{{ plano.limite_documentos }}</td>
          <td>R$ {{ plano.preco_mensal }}</td>
          <td>
            <button @click="edit(plano)">Editar</button>
            <button @click="remove(plano.id)">Remover</button>
          </td>
        </tr>
      </tbody>
    </table>

    <PlanoModal v-if="showModal" @save="save" @close="showModal = false" />
  </div>
</template>
```

---

## Configuração Vite — proxy para dev

```typescript
// vite.config.ts
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
      '/agents': 'http://localhost:8000',
      '/documents': 'http://localhost:8000',
    }
  }
})
```

---

## Plano de verificação

```bash
# Setup inicial
cd docagent-frontend
npm install
npm run dev

# Verificações manuais:
# 1. /login — formulário de login, redireciona para /chat após sucesso
# 2. /chat — sidebar com agent selector e file upload
# 3. Enviar mensagem — loading state, resposta em streaming aparecem
# 4. Upload PDF — feedback de chunks indexados
# 5. /sys-mgmt/login — login admin
# 6. /sys-mgmt/planos — CRUD de planos
# 7. Token expirado — redireciona para /login automaticamente

# Build de produção
npm run build
```

---

## Princípios aplicados

| Princípio | Onde |
|---|---|
| **Store por domínio** | `auth`, `adminAuth`, `agents`, `chat` — cada store tem responsabilidade única |
| **Fetch via fetch() não Axios** | SSE/streaming POST não funciona com Axios — fetch nativo com ReadableStream |
| **Cache de agentes** | `agents store` busca uma vez e reutiliza (`fetchIfNeeded`) |
| **Separação admin/user** | Tokens separados, stores separados, guards separados |
| **Proxy em dev** | Vite proxy evita CORS em desenvolvimento sem mudar a API |
| **sessionStorage** | Auth persistida na sessão do navegador (apagada ao fechar a aba) |
