# Fase 25 — Mobile App (PWA)

## Objetivo

Transformar o frontend Vue 3 em uma Progressive Web App instalável no celular. Operadores poderão instalar o z3ndocs no smartphone e receber push notifications quando novos atendimentos chegarem — sem precisar publicar nas lojas de app.

---

## O que é PWA

Uma PWA (Progressive Web App) é um site com capacidades de app nativo:
- **Instalável:** aparece na tela inicial do celular como um app
- **Offline:** cache de recursos essenciais via Service Worker
- **Push notifications:** recebe notificações mesmo com o app fechado
- **Ícone e splash screen:** experiência idêntica a um app nativo

Vantagens vs app nativo: zero custo de publicação em loja, atualização automática com o deploy, mesmo código do frontend atual.

---

## Stack

- **`vite-plugin-pwa`** — gera Service Worker e manifest automaticamente
- **Web Push API** — notificações push (suportado em Android Chrome; iOS Safari 17+)
- **`web-push`** (Node.js, no build time) ou **`pywebpush`** (Python, no backend) — para enviar push

---

## 1. Configuração PWA (vite.config.ts)

```typescript
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.ico", "logo.png"],
      manifest: {
        name: "z3ndocs",
        short_name: "z3ndocs",
        description: "Plataforma de agentes IA para atendimento",
        theme_color: "#1e293b",
        background_color: "#0f172a",
        display: "standalone",
        orientation: "portrait",
        start_url: "/",
        icons: [
          { src: "icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icons/icon-512.png", sizes: "512x512", type: "image/png" },
          {
            src: "icons/icon-512-maskable.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg,woff2}"],
        runtimeCaching: [
          {
            // Cache de API: stale-while-revalidate para listas
            urlPattern: /^https:\/\/.*\/api\/agentes/,
            handler: "StaleWhileRevalidate",
            options: { cacheName: "api-agentes", expiration: { maxAgeSeconds: 300 } },
          },
          {
            // API de chat: network-only (sempre fresco)
            urlPattern: /^https:\/\/.*\/api\/chat/,
            handler: "NetworkOnly",
          },
        ],
      },
    }),
  ],
});
```

---

## 2. Push Notifications

### Fluxo

```
1. Usuário acessa o app e aceita notificações
2. Frontend: navigator.serviceWorker + PushManager.subscribe()
   → Gera subscription object (endpoint + keys)
3. Frontend: POST /api/push/subscribe com o subscription object
4. Backend: salva na tabela push_subscription
5. Evento ocorre (novo atendimento, etc.)
6. Backend: pywebpush → VAPID → envia push para o endpoint
7. Service Worker recebe push → exibe notificação
8. Usuário toca na notificação → abre o app na tela certa
```

### Geração de chaves VAPID

```bash
# Gerar par de chaves VAPID (uma vez, salvar em .env)
python -c "
from py_vapid import Vapid
v = Vapid()
v.generate_keys()
print('VAPID_PRIVATE_KEY:', v.private_key)
print('VAPID_PUBLIC_KEY:', v.public_key)
"
```

### Schema — `push_subscription`

```python
class PushSubscription(Base):
    __tablename__ = "push_subscription"

    id: int (PK)
    usuario_id: int (FK → usuario)
    tenant_id: int (FK → tenant)
    endpoint: str (TEXT, UNIQUE)         # URL do push service
    p256dh: str                          # chave pública de criptografia
    auth: str                            # chave de autenticação
    user_agent: str | None               # para debug
    created_at: datetime
    last_used_at: datetime | None
```

### PushService (backend)

```python
from pywebpush import webpush, WebPushException

class PushService:

    @staticmethod
    async def registrar(
        usuario_id: int,
        tenant_id: int,
        subscription: dict,  # {"endpoint": ..., "keys": {"p256dh": ..., "auth": ...}}
        db: AsyncSession
    ) -> None:
        # Upsert: se endpoint já existe, atualiza; senão, cria
        existing = await db.execute(
            select(PushSubscription).where(PushSubscription.endpoint == subscription["endpoint"])
        )
        if existing.scalar_one_or_none():
            return
        db.add(PushSubscription(
            usuario_id=usuario_id,
            tenant_id=tenant_id,
            endpoint=subscription["endpoint"],
            p256dh=subscription["keys"]["p256dh"],
            auth=subscription["keys"]["auth"],
        ))

    @staticmethod
    async def enviar(
        subscriptions: list[PushSubscription],
        titulo: str,
        corpo: str,
        url: str | None = None,
        db: AsyncSession = None
    ) -> None:
        payload = json.dumps({"title": titulo, "body": corpo, "url": url})
        mortos = []
        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=payload,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": f"mailto:{settings.ADMIN_EMAIL}"},
                )
                sub.last_used_at = datetime.utcnow()
            except WebPushException as e:
                if e.response and e.response.status_code in (404, 410):
                    mortos.append(sub)  # endpoint expirado
        # Remove subscriptions mortas
        for s in mortos:
            await db.delete(s)

    @staticmethod
    async def notificar_tenant(
        tenant_id: int,
        titulo: str,
        corpo: str,
        url: str | None,
        db: AsyncSession
    ) -> None:
        subs = await db.execute(
            select(PushSubscription).where(PushSubscription.tenant_id == tenant_id)
        )
        await PushService.enviar(subs.scalars().all(), titulo, corpo, url, db)
```

### Endpoints

```
POST /api/push/subscribe
    → Recebe subscription object do frontend
    → Salva na tabela push_subscription

DELETE /api/push/subscribe
    → Remove subscription do usuário atual

GET /api/push/vapid-key
    → Retorna VAPID_PUBLIC_KEY (necessário para o frontend se inscrever)
```

### Triggers de notificação

```python
# Em atendimento/router.py — quando novo atendimento criado:
await PushService.notificar_tenant(
    tenant_id=tenant_id,
    titulo="Novo atendimento",
    corpo=f"Mensagem de {numero} via {canal}",
    url=f"/atendimentos/{atendimento.id}",
    db=db
)

# Quando atendimento fica urgente (prioridade URGENTE):
await PushService.notificar_tenant(
    tenant_id=tenant_id,
    titulo="⚠️ Atendimento urgente",
    corpo=f"Operador solicitado em atendimento {atendimento.id}",
    url=f"/atendimentos/{atendimento.id}",
    db=db
)
```

---

## 3. Service Worker — Notificações

```javascript
// public/sw.js (ou gerado pelo vite-plugin-pwa)

self.addEventListener("push", (event) => {
  const data = event.data?.json() ?? {};
  const options = {
    body: data.body,
    icon: "/icons/icon-192.png",
    badge: "/icons/badge-72.png",
    data: { url: data.url },
    vibrate: [200, 100, 200],
    actions: [
      { action: "abrir", title: "Ver atendimento" },
      { action: "fechar", title: "Fechar" },
    ],
  };
  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  if (event.action === "abrir" || !event.action) {
    const url = event.notification.data?.url || "/";
    event.waitUntil(clients.openWindow(url));
  }
});
```

---

## 4. Frontend — Permissão de Notificações

### useNotifications composable

```typescript
// src/composables/useNotifications.ts
export function useNotifications() {
  const isSupported = "Notification" in window && "serviceWorker" in navigator;
  const permission = ref(Notification.permission); // 'default' | 'granted' | 'denied'

  async function solicitar(): Promise<boolean> {
    if (!isSupported) return false;
    const result = await Notification.requestPermission();
    permission.value = result;
    if (result === "granted") {
      await registrarSubscription();
    }
    return result === "granted";
  }

  async function registrarSubscription(): Promise<void> {
    const vapidKey = await api.get("/push/vapid-key");
    const sw = await navigator.serviceWorker.ready;
    const sub = await sw.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapidKey.data.key),
    });
    await api.post("/push/subscribe", sub.toJSON());
  }

  return { isSupported, permission, solicitar };
}
```

### Banner de ativação

Em `AppLayout.vue`, exibir banner após login se `permission === 'default'`:

```
┌─────────────────────────────────────────────────────────┐
│ 🔔 Ative notificações para ser avisado de novos         │
│    atendimentos mesmo com o app fechado.                │
│    [Ativar notificações]           [Agora não]          │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Ícones e Splash Screen

Gerar ícones em múltiplos tamanhos a partir do logo z3ndocs:
- 192x192, 512x512 (padrão)
- 512x512 maskable (para Android Adaptive Icons)
- 180x180 (Apple Touch Icon)
- 72x72 (badge para notificações)

Ferramentas: `pwa-asset-generator` ou Figma export.

---

## 6. Suporte iOS (Safari)

iOS Safari 17+ suporta Web Push. Algumas particularidades:
- Requer HTTPS (já temos via Cloudflare)
- O usuário precisa adicionar à tela inicial ANTES de aceitar notificações
- Exibir instrução especial para usuários iOS:

```typescript
const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
const isStandalone = window.matchMedia("(display-mode: standalone)").matches;

if (isIOS && !isStandalone) {
  // Exibir: "Para receber notificações no iPhone,
  //          primeiro adicione este app à tela inicial:
  //          toque em [ícone compartilhar] → 'Adicionar à Tela de Início'"
}
```

---

## Dependências

**Backend:**
```toml
dependencies = [
    "pywebpush>=2.0.0",
    "py-vapid>=1.9.0",
]
```

**Frontend:**
```json
{
  "devDependencies": {
    "vite-plugin-pwa": "^0.19.0"
  }
}
```

---

## Variáveis de Ambiente

```env
VAPID_PRIVATE_KEY=<gerado pelo py_vapid>
VAPID_PUBLIC_KEY=<gerado pelo py_vapid>
ADMIN_EMAIL=admin@z3ndocs.uk   # required pelo protocolo VAPID
```

---

## Testes

```
tests/test_pwa/
├── test_push_service.py
│   ├── test_registrar_subscription
│   ├── test_upsert_endpoint_existente
│   ├── test_enviar_notificacao           — mock pywebpush
│   ├── test_remove_subscription_morta    — status 410 → deleta
│   └── test_notificar_tenant
└── test_push_router.py
    ├── test_subscribe_salva_no_banco
    ├── test_unsubscribe_remove
    └── test_vapid_key_retorna_chave_publica
```

---

## Ordem de Implementação

```
1.  Branch: fase-25
2.  Gerar chaves VAPID + adicionar ao .env.cloudflare
3.  Gerar ícones PWA a partir do logo z3ndocs
4.  vite-plugin-pwa: instalar + configurar vite.config.ts
5.  Alembic: tabela push_subscription
6.  push/models.py + schemas.py
7.  🔴 RED: test_push_service.py
8.  🟢 GREEN: push/services.py (PushService)
9.  push/router.py + api.py registrar
10. Instrumentar notificações: novo atendimento + urgente
11. Frontend: useNotifications composable
12. Frontend: banner de ativação em AppLayout
13. Frontend: instrução especial para iOS
14. Testar instalação no Android + iOS
```

---

## Gotchas

- **HTTPS obrigatório:** Service Workers só funcionam em HTTPS. No dev local usar `https://localhost` (vite --https) ou testar diretamente na produção.
- **Firefox:** suporta PWA e push, mas não suporta `display: standalone` no desktop (ainda abre como aba).
- **Subscriptions expiram:** endpoints de push expiram silenciosamente. Sempre tratar status 404/410 removendo a subscription do banco.
- **Rate limit de push:** Google FCM (Chrome) e Apple APNs têm rate limits. Não enviar push para cada mensagem de chat — só eventos importantes (novo atendimento, urgente).
- **Offline:** o app em modo offline mostra lista de atendimentos cacheada. Não permitir ações (assumir, encerrar) offline — exibir "Sem conexão" elegante.
