import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAdminAuthStore } from '@/stores/adminAuth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // Publicas
    { path: '/login', name: 'login', component: () => import('@/views/auth/LoginView.vue') },
    {
      path: '/forgot-password',
      name: 'forgot-password',
      component: () => import('@/views/auth/ForgotPasswordView.vue'),
    },
    {
      path: '/reset-password',
      name: 'reset-password',
      component: () => import('@/views/auth/ResetPasswordView.vue'),
    },

    // Autenticadas
    {
      path: '/',
      redirect: '/conversa',
    },
    {
      path: '/conversa',
      name: 'chat',
      component: () => import('@/views/chat/ChatView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/configuracoes',
      name: 'configuracoes',
      component: () => import('@/views/user/SettingsView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/agentes',
      name: 'agentes',
      component: () => import('@/views/agentes/AgentesView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/whatsapp',
      name: 'whatsapp',
      component: () => import('@/views/whatsapp/WhatsappView.vue'),
      meta: { requiresAuth: true },
    },

    // Admin
    {
      path: '/sys-mgmt/login',
      name: 'admin-login',
      component: () => import('@/views/admin/AdminLoginView.vue'),
    },
    {
      path: '/sys-mgmt',
      component: () => import('@/views/admin/AdminLayoutView.vue'),
      meta: { requiresAdmin: true },
      children: [
        { path: '', redirect: '/sys-mgmt/tenants' },
        {
          path: 'tenants',
          name: 'admin-tenants',
          component: () => import('@/views/admin/AdminTenantsView.vue'),
        },
        {
          path: 'planos',
          name: 'admin-planos',
          component: () => import('@/views/admin/AdminPlanosView.vue'),
        },
        {
          path: 'assinaturas',
          name: 'admin-assinaturas',
          component: () => import('@/views/admin/AdminAssinaturasView.vue'),
        },
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
