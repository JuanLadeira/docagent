# Fase 24 — Canal E-mail & Integrações n8n

## Objetivo

Adicionar e-mail como terceiro canal de atendimento (junto com WhatsApp e Telegram) e expor webhooks estruturados para o n8n (que já roda no Docker Compose) criar automações sem código. Os atendimentos por e-mail aparecem na mesma fila unificada com badge `EM`.

---

## Parte 1 — Canal E-mail

### Como funciona

```
Cliente envia e-mail para suporte@empresa.z3ndocs.uk
  → Mailgun recebe (MX do domínio aponta para Mailgun)
  → Mailgun faz POST /api/email/webhook (inbound parsing)
  → Backend: extrai remetente, assunto, corpo
  → Cria/retoma Atendimento (canal=EMAIL)
  → Executa agente
  → Responde via Mailgun API (reply no mesmo thread)
```

### Schema — Nova tabela: `email_instancia`

```python
class EmailInstancia(Base):
    __tablename__ = "email_instancia"

    id: int (PK)
    tenant_id: int (FK → tenant)
    agente_id: int | None (FK → agente)

    # Configuração do endereço
    email_entrada: str          # ex: suporte@empresa.z3ndocs.uk
    nome_exibicao: str          # ex: "Suporte z3ndocs"
    mailgun_domain: str         # ex: empresa.z3ndocs.uk
    mailgun_api_key: str        # EncryptedString

    # Comportamento
    cria_atendimentos: bool = True
    assinatura_email: str | None  # texto de assinatura nas respostas

    status: EmailInstanciaStatus   # ATIVA | INATIVA
    webhook_configurado: bool = False
    created_at: datetime
    updated_at: datetime

class EmailInstanciaStatus(str, Enum):
    ATIVA = "ativa"
    INATIVA = "inativa"
```

### Mudanças em `atendimento`

```python
class Atendimento(Base):
    # campos existentes (instancia_id, telegram_instancia_id)...
    email_instancia_id: int | None (FK → email_instancia)
    canal: CanalAtendimento  # + EMAIL

class CanalAtendimento(str, Enum):
    WHATSAPP = "WHATSAPP"
    TELEGRAM = "TELEGRAM"
    EMAIL = "EMAIL"       # novo
```

### EmailService

```python
class EmailService:

    async def criar_instancia(data: EmailInstanciaCreate, tenant_id, db) -> EmailInstancia
    async def listar_instancias(tenant_id, db) -> list[EmailInstancia]
    async def deletar_instancia(instancia_id, tenant_id, db) -> None

    async def enviar_resposta(
        instancia: EmailInstancia,
        destinatario: str,
        assunto: str,
        corpo_html: str,
        message_id_original: str | None,  # para threading (In-Reply-To header)
    ) -> None:
        # POST https://api.mailgun.net/v3/{domain}/messages
        # Headers: In-Reply-To + References para manter thread

    async def processar_inbound(payload: dict, db) -> None:
        # Extrai: sender, subject, body-plain, Message-ID, In-Reply-To
        # Busca EmailInstancia pelo recipient
        # Cria/retoma Atendimento
        # Executa agente
        # Envia resposta via enviar_resposta()
```

### Webhook Inbound (Mailgun)

```python
# POST /api/email/webhook
async def email_inbound_webhook(request: Request, db: AsyncSession):
    # Mailgun envia multipart/form-data
    form = await request.form()

    # Validar assinatura Mailgun
    timestamp = form.get("timestamp")
    token = form.get("token")
    signature = form.get("signature")
    _validar_assinatura_mailgun(timestamp, token, signature)

    payload = {
        "sender": form.get("sender"),
        "recipient": form.get("recipient"),
        "subject": form.get("subject"),
        "body": form.get("body-plain"),
        "html": form.get("body-html"),
        "message_id": form.get("Message-Id"),
        "in_reply_to": form.get("In-Reply-To"),
    }
    await EmailService.processar_inbound(payload, db)
    return {"status": "ok"}
```

### Threading de E-mail

Para manter respostas no mesmo thread (importante para UX):

- Salvar `message_id` do e-mail original no `Atendimento` (campo `email_thread_id`)
- Ao responder: incluir `In-Reply-To: {email_thread_id}` e `References: {email_thread_id}`
- O cliente de e-mail do usuário agrupa automaticamente como thread

### Endpoints

```
GET  /api/email/instancias              → lista instâncias do tenant
POST /api/email/instancias              → cria + configura MX (instrução para o usuário)
PUT  /api/email/instancias/{id}         → atualiza agente_id, assinatura
DELETE /api/email/instancias/{id}       → remove
POST /api/email/webhook                 → inbound Mailgun (público)
POST /api/email/instancias/{id}/testar  → envia e-mail de teste para o admin
```

### Frontend — EmailView.vue

Espelha `TelegramView.vue`. Diferenças:
- Campo `email_entrada` ao invés de bot_token
- Exibe instruções de configuração de DNS (MX records) após criar
- Textarea de assinatura de e-mail
- Badge `EM` (cor roxa) na lista de atendimentos

---

## Parte 2 — Integrações n8n

O n8n já roda no Docker Compose (porta 5678). Esta fase expõe webhooks estruturados e documenta os workflows mais úteis.

### Webhooks de saída (DocAgent → n8n)

Criar um sistema de webhooks de evento que o tenant pode configurar:

```python
class WebhookConfig(Base):
    __tablename__ = "webhook_config"

    id: int (PK)
    tenant_id: int (FK)
    evento: WebhookEvento
    url_destino: str            # URL do n8n webhook node
    segredo: str                # EncryptedString — para assinar o payload
    ativo: bool = True
    created_at: datetime

class WebhookEvento(str, Enum):
    ATENDIMENTO_CRIADO = "atendimento.criado"
    ATENDIMENTO_ENCERRADO = "atendimento.encerrado"
    ATENDIMENTO_HUMANO = "atendimento.humano"
    DOCUMENTO_INGERIDO = "documento.ingerido"
    FINE_TUNE_CONCLUIDO = "fine_tune.concluido"
    QUOTA_EXCEDIDA = "quota.excedida"
```

### WebhookDispatcher

```python
class WebhookDispatcher:

    @staticmethod
    async def disparar(
        tenant_id: int,
        evento: WebhookEvento,
        payload: dict,
        db: AsyncSession
    ) -> None:
        configs = await _listar_configs_ativas(tenant_id, evento, db)
        for config in configs:
            # Assina o payload com HMAC-SHA256 usando config.segredo
            assinatura = _assinar(payload, config.segredo)
            # Dispara via Celery task (não bloqueia)
            enviar_webhook_task.delay(config.url_destino, payload, assinatura)

@celery.task(max_retries=3, default_retry_delay=60)
def enviar_webhook_task(url: str, payload: dict, assinatura: str):
    response = requests.post(
        url,
        json=payload,
        headers={"X-DocAgent-Signature": assinatura},
        timeout=10
    )
    response.raise_for_status()
```

Retry automático (3 tentativas, intervalo de 60s) via Celery.

### Endpoints de configuração de webhooks

```
GET    /api/webhooks/configs            → lista configs do tenant
POST   /api/webhooks/configs            → cria nova config (evento + url + segredo)
PUT    /api/webhooks/configs/{id}       → atualiza
DELETE /api/webhooks/configs/{id}       → remove
POST   /api/webhooks/configs/{id}/testar → dispara payload de teste
```

### Workflows n8n sugeridos (templates)

Documentar no `/docs` da plataforma:

**1. Novo atendimento → notificar Slack**
```
Trigger: Webhook (atendimento.criado)
  → Slack: "Novo atendimento de {numero} no {canal}"
```

**2. Atendimento encerrado → atualizar CRM**
```
Trigger: Webhook (atendimento.encerrado)
  → HTTP Request → HubSpot / Pipedrive API
  → Atualizar contato com histórico
```

**3. Quota excedida → email para dono do tenant**
```
Trigger: Webhook (quota.excedida)
  → Email (Gmail node): "Você atingiu o limite de agentes do seu plano"
  → Incluir link para upgrade
```

**4. Fine-tune concluído → notificar responsável**
```
Trigger: Webhook (fine_tune.concluido)
  → Telegram / WhatsApp: "Seu modelo {modelo_saida} está pronto!"
```

**5. Documento ingerido → planilha Google Sheets**
```
Trigger: Webhook (documento.ingerido)
  → Google Sheets: adicionar linha com nome, agente, data, chunks
```

---

## Frontend — WebhooksView.vue

```
┌────────────────────────────────────────────────────────────┐
│ Integrações & Webhooks                    [+ Nova Config]  │
│                                                            │
│ ┌──────────────────────────────────────────────────────┐   │
│ │ atendimento.criado     https://n8n.../webhook/xxx  ✓ │   │
│ │ atendimento.encerrado  https://n8n.../webhook/yyy  ✓ │   │
│ │ quota.excedida         https://zapier.com/hooks/... ✓ │  │
│ └──────────────────────────────────────────────────────┘   │
│                                                            │
│ [Ver documentação de payloads]                             │
└────────────────────────────────────────────────────────────┘
```

---

## Dependências

```toml
dependencies = [
    "mailgun2>=0.1.0",  # ou requests direto para Mailgun API
]
```

---

## Ordem de Implementação

```
1.  Branch: fase-24
2.  Alembic: email_instancia + webhook_config + canal EMAIL em atendimento
3.  email/models.py + schemas.py + services.py
4.  email/router.py: CRUD + webhook inbound
5.  AtendimentoService: suporte a canal=EMAIL
6.  Frontend: EmailView.vue + badge EM na AtendimentoView
7.  webhook_config/models.py + WebhookDispatcher
8.  Instrumentar eventos: disparar webhook nos pontos chave
9.  webhook_config/router.py: CRUD configs + testar
10. Frontend: WebhooksView.vue
11. Documentação: payloads de cada evento
```

---

## Gotchas

- **Mailgun MX records:** o tenant precisa configurar DNS para receber e-mail. Criar guia passo a passo na UI.
- **Spam/SPF/DKIM:** configurar registros SPF e DKIM no Mailgun para não cair em spam nas respostas.
- **Tamanho do e-mail:** e-mails podem ter HTML pesado. Processar só `body-plain` para o agente. Truncar em 4000 chars se necessário.
- **Webhook retry:** usar Celery com retry e dead letter queue — nunca perder um evento de webhook.
- **Segredo de webhook:** usar HMAC-SHA256 (padrão GitHub/Stripe) para que o n8n possa validar a origem.
- **n8n URL interna:** se n8n está no mesmo Docker Compose, a URL é `http://n8n:5678/webhook/...` — internamente sem passar pelo Cloudflare.
