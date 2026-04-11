# Fase 17 — Planos, Assinaturas & Billing

## Objetivo

Finalizar o sistema de monetização do z3ndocs: planos com limites de uso, assinaturas por tenant com ciclo de renovação, integração real com Stripe para pagamentos, grace period pós-vencimento e painel admin de faturamento.

---

## O que já está implementado

| O quê | Onde | Estado |
|-------|------|--------|
| `Plano` model + CRUD admin | `plano/models.py`, `admin/router.py` | ✅ |
| `Assinatura` model (parcial) | `assinatura/models.py` | ✅ campos base, ❌ status/grace |
| `AssinaturaService` | `assinatura/services.py` | ✅ get_by_tenant, criar, checar_quota, uso_atual |
| `require_quota` dependency | `dependencies.py` | ✅ |
| Router tenant | `assinatura/router.py` | ✅ GET /me, GET /me/uso, POST / |
| Router admin | `admin/router.py` | ✅ GET /assinaturas, POST /tenants/{id}/assinatura, CRUD /planos |
| Testes TDD | `tests/test_fase17/` | ✅ service + router + quota |

## O que falta implementar

- `Assinatura`: campos `status`, `stripe_customer_id`, `stripe_price_id`, `grace_period_ate`, `cancelada_em`
- `Plano`: campo `stripe_price_id`
- Módulo `fatura/` (model + service)
- Módulo `pagamento/` (PaymentService com Stripe SDK)
- Módulo `email/` (EmailService com Resend)
- Webhook Stripe (`POST /api/webhooks/stripe`)
- Endpoints `/checkout`, `/portal`, `/me/faturas`
- Grace period logic + cron APScheduler
- `require_quota` atualizado para checar `status` (não só `ativo`)
- Admin: endpoint `POST /assinaturas/{id}/renovar` + `DELETE /assinaturas/{id}`
- Frontend: banner de grace period + melhorias AdminAssinaturasView

---

## Schema — Mudanças nos modelos existentes

### Plano — adicionar `stripe_price_id`

```python
class Plano(Base):
    __tablename__ = "planos"
    # campos existentes: nome, descricao, limite_agentes, limite_documentos,
    # limite_sessoes, ciclo_dias, preco_mensal, ativo

    # NOVO:
    stripe_price_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Preenchido pelo admin via Stripe dashboard → usado no criar_subscription
```

### Assinatura — migrar `ativo: bool` para `status: AssinaturaStatus`

O model atual tem `ativo: bool`. A migração troca isso por um enum de status mais rico.

**Estratégia de migração Alembic:**
```python
# Migration: adicionar coluna status + novos campos, depois popular status a partir de ativo
def upgrade():
    with op.batch_alter_table("assinatura") as batch:
        # Novos campos Stripe
        batch.add_column(sa.Column("stripe_customer_id", sa.String(100), nullable=True))
        batch.add_column(sa.Column("stripe_price_id", sa.String(100), nullable=True))
        # Status (começa como VARCHAR para SQLite)
        batch.add_column(sa.Column("status", sa.String(20), nullable=False, server_default="ativa"))
        # Grace period
        batch.add_column(sa.Column("grace_period_ate", sa.DateTime, nullable=True))
        batch.add_column(sa.Column("cancelada_em", sa.DateTime, nullable=True))
        # Remover ativo (depois de popular status)
        # Não remover imediatamente — manter ativo até migração de dados
    
    # Popular status a partir de ativo
    op.execute("""
        UPDATE assinatura SET status = CASE WHEN ativo = 1 THEN 'ativa' ELSE 'vencida' END
    """)
    # Após confirmar dados, pode-se remover a coluna ativo em migration futura
```

```python
class AssinaturaStatus(str, Enum):
    ATIVA = "ativa"
    GRACE = "grace"        # pagamento falhou, acesso por X dias ainda
    VENCIDA = "vencida"    # sem acesso
    CANCELADA = "cancelada"

class Assinatura(Base):
    __tablename__ = "assinatura"

    # campos existentes:
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"))
    plano_id: Mapped[int] = mapped_column(ForeignKey("planos.id"))
    data_inicio: Mapped[datetime]
    data_proxima_renovacao: Mapped[datetime]

    # substitui ativo: bool
    status: Mapped[str] = mapped_column(String(20), default=AssinaturaStatus.ATIVA)

    # novos campos Stripe
    stripe_customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stripe_price_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # grace period
    grace_period_ate: Mapped[datetime | None] = mapped_column(nullable=True)
    cancelada_em: Mapped[datetime | None] = mapped_column(nullable=True)
```

---

## Nova tabela: `fatura`

```python
class FaturaStatus(str, Enum):
    PAGA = "paga"
    PENDENTE = "pendente"
    FALHOU = "falhou"

class Fatura(Base):
    __tablename__ = "fatura"

    id: int (PK)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"))
    assinatura_id: Mapped[int] = mapped_column(ForeignKey("assinatura.id"))
    stripe_invoice_id: Mapped[str] = mapped_column(String(100), unique=True)  # idempotência
    valor_centavos: Mapped[int]
    status: Mapped[str] = mapped_column(String(20), default=FaturaStatus.PENDENTE)
    periodo_inicio: Mapped[datetime]
    periodo_fim: Mapped[datetime]
    pdf_url: Mapped[str | None] = mapped_column(nullable=True)   # URL da fatura no Stripe
    pago_em: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime]
```

---

## Integração Stripe

### Fluxo de assinatura nova

```
1. Admin cria Plano com stripe_price_id (copiado do Stripe dashboard)
2. Tenant acessa /configurações → "Upgrade de plano"
3. POST /api/assinaturas/checkout {plano_id}
4. Backend: cria Stripe Customer (se não existir) → cria Stripe Subscription
5. Retorna {checkout_url} → frontend redireciona para Stripe Checkout
6. Stripe processa pagamento → dispara webhook
7. Backend: invoice.payment_succeeded → ativa Assinatura + cria Fatura + email
```

### PaymentService (`pagamento/services.py`)

```python
class PaymentService:

    @staticmethod
    async def criar_ou_obter_customer(tenant: Tenant) -> str:
        """Cria Customer no Stripe se não existir. Retorna stripe_customer_id."""
        if tenant.assinatura and tenant.assinatura.stripe_customer_id:
            return tenant.assinatura.stripe_customer_id
        customer = stripe.Customer.create(
            email=tenant.owner_email,  # buscar do usuário OWNER do tenant
            name=tenant.nome,
            metadata={"tenant_id": str(tenant.id)},
        )
        return customer.id

    @staticmethod
    async def criar_subscription(customer_id: str, price_id: str, trial_days: int = 0) -> dict:
        """Cria Subscription no Stripe. Retorna subscription object."""
        params = {
            "customer": customer_id,
            "items": [{"price": price_id}],
            "payment_behavior": "default_incomplete",
            "expand": ["latest_invoice.payment_intent"],
        }
        if trial_days > 0:
            params["trial_period_days"] = trial_days
        return stripe.Subscription.create(**params)

    @staticmethod
    async def cancelar_subscription(subscription_id: str) -> None:
        """Cancela ao fim do período atual (não imediatamente)."""
        stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)

    @staticmethod
    async def criar_portal_session(customer_id: str, return_url: str) -> str:
        """Retorna URL do portal Stripe onde o tenant gerencia cartão e histórico."""
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return session.url

    @staticmethod
    async def sincronizar_subscription(subscription_id: str) -> dict:
        """Busca subscription atual no Stripe (para reconciliação)."""
        return stripe.Subscription.retrieve(subscription_id)
```

### Webhook Stripe (`POST /api/webhooks/stripe`)

```python
# Endpoint público — sem JWT, mas valida stripe-signature
@router.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request, db: AsyncSession):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Assinatura Stripe inválida")

    match event["type"]:

        case "invoice.payment_succeeded":
            invoice = event["data"]["object"]
            await _handle_payment_succeeded(invoice, db)

        case "invoice.payment_failed":
            invoice = event["data"]["object"]
            await _handle_payment_failed(invoice, db)

        case "customer.subscription.deleted":
            subscription = event["data"]["object"]
            await _handle_subscription_deleted(subscription, db)

        case "customer.subscription.updated":
            subscription = event["data"]["object"]
            await _handle_subscription_updated(subscription, db)

    return {"status": "ok"}


async def _handle_payment_succeeded(invoice: dict, db: AsyncSession):
    stripe_invoice_id = invoice["id"]
    customer_id = invoice["customer"]
    subscription_id = invoice["subscription"]

    # Busca assinatura pelo stripe_customer_id
    assinatura = await AssinaturaService(db).get_by_stripe_customer(customer_id)
    if not assinatura:
        return  # cliente não encontrado — ignorar

    # Idempotência: não duplicar fatura já registrada
    fatura_existente = await FaturaService(db).get_by_stripe_invoice_id(stripe_invoice_id)
    if fatura_existente:
        return

    # Ativa/normaliza assinatura
    assinatura.status = AssinaturaStatus.ATIVA
    assinatura.grace_period_ate = None
    assinatura.data_proxima_renovacao = datetime.fromtimestamp(
        invoice["lines"]["data"][0]["period"]["end"]
    )

    # Cria fatura local
    await FaturaService(db).criar(
        tenant_id=assinatura.tenant_id,
        assinatura_id=assinatura.id,
        stripe_invoice_id=stripe_invoice_id,
        valor_centavos=invoice["amount_paid"],
        periodo_inicio=...,
        periodo_fim=...,
        pdf_url=invoice.get("invoice_pdf"),
        status=FaturaStatus.PAGA,
        pago_em=datetime.utcnow(),
    )

    # Email de confirmação
    await EmailService.enviar_confirmacao_pagamento(assinatura.tenant, fatura)
    await db.commit()


async def _handle_payment_failed(invoice: dict, db: AsyncSession):
    customer_id = invoice["customer"]
    assinatura = await AssinaturaService(db).get_by_stripe_customer(customer_id)
    if not assinatura:
        return

    grace_days = int(await SystemConfigService.get("grace_period_days", default="3"))
    assinatura.status = AssinaturaStatus.GRACE
    assinatura.grace_period_ate = datetime.utcnow() + timedelta(days=grace_days)

    await EmailService.enviar_aviso_vencimento(assinatura.tenant, dias_restantes=grace_days)
    await db.commit()


async def _handle_subscription_deleted(subscription: dict, db: AsyncSession):
    subscription_id = subscription["id"]
    assinatura = await AssinaturaService(db).get_by_stripe_subscription(subscription_id)
    if not assinatura:
        return
    assinatura.status = AssinaturaStatus.CANCELADA
    assinatura.cancelada_em = datetime.utcnow()
    await EmailService.enviar_cancelamento(assinatura.tenant)
    await db.commit()


async def _handle_subscription_updated(subscription: dict, db: AsyncSession):
    # Sincroniza mudanças de plano (upgrade/downgrade pelo portal Stripe)
    subscription_id = subscription["id"]
    assinatura = await AssinaturaService(db).get_by_stripe_subscription(subscription_id)
    if not assinatura:
        return
    novo_price_id = subscription["items"]["data"][0]["price"]["id"]
    novo_plano = await PlanoService(db).get_by_stripe_price_id(novo_price_id)
    if novo_plano:
        assinatura.plano_id = novo_plano.id
        assinatura.stripe_price_id = novo_price_id
    await db.commit()
```

---

## Grace Period

Quando `invoice.payment_failed` é recebido:

```
Assinatura.status = GRACE
Assinatura.grace_period_ate = now() + GRACE_PERIOD_DAYS (padrão: 3)

Durante GRACE:
  - Acesso ao sistema mantido
  - Banner de aviso no frontend: "Seu pagamento falhou. Acesso encerra em X dias."
  - Emails diários de lembrete (cron)
  - require_quota injeta header X-Quota-Warning: grace_period (não bloqueia)

Após grace_period_ate expirar (cron diário):
  - Assinatura.status = VENCIDA
  - require_quota retorna HTTP 402
  - Email de bloqueio de acesso
```

---

## Renovação Automática (Cron — APScheduler)

O Stripe cuida da cobrança automática. O cron é apenas uma rede de segurança para webhooks perdidos:

```python
# api.py — lifespan
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        cron_reconciliar_assinaturas,
        trigger="cron",
        hour=3,      # 3h da manhã
        minute=0,
    )
    scheduler.start()
    yield
    scheduler.shutdown()


async def cron_reconciliar_assinaturas():
    async with get_async_session() as db:
        agora = datetime.utcnow()

        # 1. GRACE expirado → VENCIDA
        assinaturas_grace = await db.execute(
            select(Assinatura).where(
                Assinatura.status == AssinaturaStatus.GRACE,
                Assinatura.grace_period_ate < agora,
            )
        )
        for a in assinaturas_grace.scalars():
            a.status = AssinaturaStatus.VENCIDA
            await EmailService.enviar_bloqueio_acesso(a.tenant)

        # 2. ATIVA com renovação atrasada → sincronizar com Stripe
        atrasadas = await db.execute(
            select(Assinatura).where(
                Assinatura.status == AssinaturaStatus.ATIVA,
                Assinatura.data_proxima_renovacao < agora,
                Assinatura.stripe_subscription_id.isnot(None),
            )
        )
        for a in atrasadas.scalars():
            sub = await PaymentService.sincronizar_subscription(a.stripe_subscription_id)
            if sub["status"] == "active":
                a.data_proxima_renovacao = datetime.fromtimestamp(sub["current_period_end"])
            elif sub["status"] in ("past_due", "unpaid"):
                a.status = AssinaturaStatus.GRACE
                a.grace_period_ate = agora + timedelta(days=3)

        await db.commit()
```

---

## `require_quota` atualizado

O `require_quota` atual em `dependencies.py` usa `checar_quota()` que ignora o `status`. Após adicionar o campo status:

```python
# dependencies.py — atualizado
def require_quota(recurso: str):
    async def _check(
        current_user: CurrentUser,
        assinatura_service: AssinaturaServiceDep,
    ) -> None:
        assinatura = await assinatura_service.get_by_tenant(current_user.tenant_id)

        # Sem assinatura: modo demo (acesso livre)
        if assinatura is None:
            return

        # VENCIDA ou CANCELADA: bloqueia
        if assinatura.status in (AssinaturaStatus.VENCIDA, AssinaturaStatus.CANCELADA):
            raise HTTPException(402, "Assinatura inativa. Renove para continuar.")

        # GRACE: permite mas avisa via header
        # (o response object não está disponível aqui — o banner vem do /me)

        # Checa limite de quantidade
        ok = await assinatura_service.checar_quota(current_user.tenant_id, recurso)
        if not ok:
            raise HTTPException(429, f"Limite de {recurso} do plano atingido.")

    return Depends(_check)
```

---

## EmailService (`email/services.py`)

Usar **Resend** (gratuito até 3.000 emails/mês):

```python
import resend

class EmailService:

    @staticmethod
    async def enviar_confirmacao_pagamento(tenant: Tenant, fatura: Fatura) -> None:
        resend.Emails.send({
            "from": "z3ndocs <noreply@z3ndocs.uk>",
            "to": [tenant.owner_email],
            "subject": "Pagamento confirmado — z3ndocs",
            "html": _template_confirmacao(tenant, fatura),
        })

    @staticmethod
    async def enviar_aviso_vencimento(tenant: Tenant, dias_restantes: int) -> None:
        resend.Emails.send({
            "from": "z3ndocs <noreply@z3ndocs.uk>",
            "to": [tenant.owner_email],
            "subject": f"Ação necessária: acesso encerra em {dias_restantes} dia(s)",
            "html": _template_aviso_vencimento(tenant, dias_restantes),
        })

    @staticmethod
    async def enviar_bloqueio_acesso(tenant: Tenant) -> None:
        resend.Emails.send({...})

    @staticmethod
    async def enviar_cancelamento(tenant: Tenant) -> None:
        resend.Emails.send({...})
```

> **Nota:** `tenant.owner_email` precisa ser obtido buscando o usuário com `role=OWNER` do tenant.

---

## Endpoints completos

```
# Tenant
GET    /api/assinaturas/me               → AssinaturaStatusResponse (com status, grace_period_ate)
GET    /api/assinaturas/me/uso           → UsoAtualResponse
GET    /api/assinaturas/me/faturas       → list[FaturaPublic]
POST   /api/assinaturas/checkout         → {checkout_url} (Stripe Checkout)
POST   /api/assinaturas/portal           → {portal_url}   (Stripe Customer Portal)

# Stripe (público)
POST   /api/webhooks/stripe              → processa eventos Stripe

# Admin
GET    /api/admin/assinaturas            → list[AssinaturaPublic] (existente)
POST   /api/admin/tenants/{id}/assinatura → criar/trocar plano (existente)
POST   /api/admin/assinaturas/{id}/renovar  → força renovação manual (sincroniza Stripe)
DELETE /api/admin/assinaturas/{id}       → cancela assinatura (status=CANCELADA)
GET    /api/admin/tenants/{id}/faturas   → histórico de faturas do tenant
```

---

## Frontend

### Banner de grace period

Em `AppLayoutView.vue` (ou componente raiz pós-login):

```vue
<template>
  <div v-if="assinatura?.status === 'grace'" class="banner-grace">
    ⚠️ Seu pagamento falhou. O acesso encerra em
    <strong>{{ diasRestantes }} dia(s)</strong>.
    <a href="/configuracoes/billing">Atualizar forma de pagamento</a>
  </div>
  <router-view />
</template>
```

### AdminAssinaturasView.vue (melhorias)

- Tabela de assinaturas com badge de status colorido:
  - `ATIVA` → verde
  - `GRACE` → laranja
  - `VENCIDA` → vermelho
  - `CANCELADA` → cinza
- Coluna `Próxima renovação` / `Grace até`
- Botão **"Ver faturas"** → modal com lista de faturas + links PDF
- Botão **"Renovar"** → `POST /api/admin/assinaturas/{id}/renovar`
- Botão **"Cancelar"** → confirmação + `DELETE /api/admin/assinaturas/{id}`
- Filtro por status

---

## Estrutura de Arquivos

```
src/docagent/
├── assinatura/
│   ├── models.py     — + AssinaturaStatus enum, status, stripe_customer_id,
│   │                     stripe_price_id, grace_period_ate, cancelada_em
│   ├── schemas.py    — + status, grace_period_ate no AssinaturaPublic
│   │                     + AssinaturaCheckoutResponse, FaturaPublic
│   ├── services.py   — + get_by_stripe_customer(), get_by_stripe_subscription()
│   └── router.py     — + /checkout, /portal, /me/faturas
├── fatura/
│   ├── __init__.py
│   ├── models.py     — Fatura, FaturaStatus
│   ├── schemas.py    — FaturaPublic
│   └── services.py   — FaturaService: criar, get_by_stripe_invoice_id, listar_por_tenant
├── pagamento/
│   ├── __init__.py
│   └── services.py   — PaymentService (Stripe SDK)
├── email/
│   ├── __init__.py
│   └── services.py   — EmailService (Resend)
├── plano/
│   └── models.py     — + stripe_price_id
│   └── services.py   — + get_by_stripe_price_id()
├── dependencies.py   — require_quota atualizado para checar status
└── api.py            — + APScheduler lifespan + webhook stripe router
```

---

## Variáveis de Ambiente

```env
STRIPE_SECRET_KEY=sk_live_...         # ou sk_test_... em dev
STRIPE_WEBHOOK_SECRET=whsec_...       # gerado no Stripe dashboard (webhook endpoint)
RESEND_API_KEY=re_...
```

---

## Dependências

```toml
dependencies = [
    "stripe>=8.0.0",
    "resend>=0.7.0",
    "apscheduler>=3.10.0",
]
```

---

## Testes

```
tests/test_fase17/
├── conftest.py                        — (existente — adicionar fixtures de Fatura)
├── test_assinatura_service.py         — (existente — adicionar: get_by_stripe_customer,
│                                         get_by_stripe_subscription)
├── test_assinatura_router.py          — (existente — adicionar: /checkout, /portal, /me/faturas)
├── test_quota_router.py               — (existente — adicionar: status VENCIDA bloqueia,
│                                         status GRACE permite)
├── test_payment_service.py            — mock stripe SDK
│   ├── test_criar_customer_novo
│   ├── test_reutiliza_customer_existente
│   ├── test_criar_subscription
│   └── test_cancelar_subscription_at_period_end
├── test_stripe_webhook.py
│   ├── test_assinatura_invalida_retorna_400      — stripe-signature inválida
│   ├── test_payment_succeeded_ativa_assinatura
│   ├── test_payment_succeeded_idempotente        — mesmo invoice_id → não duplica
│   ├── test_payment_failed_entra_em_grace
│   ├── test_subscription_deleted_cancela
│   └── test_subscription_updated_troca_plano
├── test_grace_period.py
│   ├── test_acesso_permitido_em_grace
│   ├── test_acesso_bloqueado_quando_vencida
│   ├── test_acesso_bloqueado_quando_cancelada
│   └── test_cron_move_grace_para_vencida
└── test_email_service.py              — mock Resend API
    ├── test_enviar_confirmacao_pagamento
    ├── test_enviar_aviso_vencimento
    └── test_enviar_bloqueio_acesso
```

---

## Ordem de Implementação

```
1.  Alembic: campos Assinatura (status, stripe_*, grace_period_ate, cancelada_em)
             + campo Plano (stripe_price_id) + tabela Fatura
2.  assinatura/models.py: AssinaturaStatus enum + novos campos
3.  plano/models.py: + stripe_price_id
4.  plano/services.py: + get_by_stripe_price_id()
5.  fatura/models.py + fatura/schemas.py
6.  fatura/services.py: FaturaService
7.  🔴 RED: test_payment_service.py
8.  🟢 GREEN: pagamento/services.py (PaymentService)
9.  assinatura/services.py: + get_by_stripe_customer(), get_by_stripe_subscription()
10. assinatura/router.py: + /checkout, /portal, /me/faturas
11. 🔴 RED: test_stripe_webhook.py
12. 🟢 GREEN: /api/webhooks/stripe (handlers de evento)
13. 🔴 RED: test_grace_period.py
14. 🟢 GREEN: cron APScheduler + require_quota atualizado
15. 🔴 RED: test_email_service.py
16. 🟢 GREEN: email/services.py (EmailService + Resend)
17. admin/router.py: + /assinaturas/{id}/renovar, DELETE /assinaturas/{id}, /tenants/{id}/faturas
18. dependencies.py: require_quota atualizado
19. Frontend: banner grace period (AppLayoutView)
20. Frontend: AdminAssinaturasView melhorias (badge status, faturas modal, renovar, cancelar)
21. Merge do alembic/versions/02c972d3cdb6_merge_heads.py
22. Fechar branch + PR
```

---

## Gotchas

- **Webhook Stripe em dev:** `stripe listen --forward-to localhost:8000/api/webhooks/stripe` — necessário para testar localmente sem deploy
- **Idempotência obrigatória:** Stripe pode reenviar o mesmo evento várias vezes. `stripe_invoice_id` com UNIQUE constraint na tabela `fatura` garante que `invoice.payment_succeeded` não seja processado duas vezes
- **stripe-signature:** nunca processar evento sem validar a assinatura — protege contra forjamento de webhooks
- **`cancel_at_period_end=True`:** cancelar ao fim do período (não imediatamente) dá uma última chance ao tenant de usar o que pagou. `customer.subscription.deleted` é disparado apenas quando o período acaba
- **owner_email:** `EmailService` precisa do e-mail do OWNER do tenant — buscar com `SELECT u.email FROM usuario u WHERE u.tenant_id = ? AND u.role = 'OWNER' LIMIT 1`
- **GRACE_PERIOD_DAYS via SystemConfig:** configurável pelo admin em `/api/admin/system-config` (chave `grace_period_days`, default `"3"`) sem precisar de deploy
- **APScheduler em dev:** com `reload=True` (uvicorn --reload), o scheduler pode duplicar jobs. Usar `replace_existing=True` no `add_job` ou desabilitar reload em dev quando testar o cron
- **Migração `ativo` → `status`:** não remover a coluna `ativo` na mesma migration que adiciona `status` — fazer em migration separada após confirmar dados corretos em produção
