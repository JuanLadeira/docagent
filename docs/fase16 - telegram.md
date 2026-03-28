# Fase 16 — Integração Telegram

## Objetivo

Adicionar o Telegram como segundo canal de atendimento, paralelo ao WhatsApp, de forma que:

- Atendimentos de WhatsApp e Telegram apareçam na mesma tela unificada
- Cada atendimento exiba um badge visual indicando o canal de origem (WA / TG)
- A configuração de qual bot usar fique armazenada no banco (sem variáveis de ambiente)
- Operadores possam responder para o cliente no canal correto (WhatsApp → Evolution API, Telegram → Bot API)

---

## Como o WhatsApp é integrado hoje

Para o WhatsApp, usamos a **Evolution API** — um servidor open-source auto-hospedado (roda no Docker Compose) que faz o trabalho pesado:

```
Browser/App WhatsApp ←→ Evolution API (porta 8080) ←→ Nosso backend (porta 8000)
```

O que a Evolution API faz por nós:
- Autentica o número via QR code (emula o WhatsApp Web)
- Recebe mensagens e nos envia via webhook (`POST /api/whatsapp/webhook`)
- Envia mensagens por nossa conta (`POST /message/sendText/{instance_name}`)
- Gerencia múltiplas instâncias (vários números) por conta própria

Ou seja, a Evolution API é um **intermediário** que abstrai o protocolo proprietário do WhatsApp.

---

## Como o Telegram será integrado

Para o Telegram, **não precisamos de intermediário**. O Telegram tem uma API oficial pública, a **Telegram Bot API**, que qualquer desenvolvedor pode usar diretamente:

```
Usuário Telegram ←→ Servidores Telegram ←→ Nosso backend (webhook)
```

### Por que não precisamos de Evolution API para o Telegram?

| | WhatsApp | Telegram |
|-|---------|---------|
| Protocolo | Proprietário (sem API oficial) | API REST pública e documentada |
| Autenticação | QR code (sessão do app) | Token de bot (gerado via @BotFather) |
| Intermediário necessário | Sim (Evolution API, Baileys, etc.) | Não — chamada direta para `api.telegram.org` |
| Custo da integração | Depende de servidor Evolution API | Zero (API gratuita e sem limites razoáveis) |

### Como funciona o Telegram Bot API

1. **Criar o bot:** No Telegram, conversar com `@BotFather` → `/newbot` → recebe um token como `123456:ABCdef...`

2. **Registrar webhook:** Uma chamada HTTP nossa para o Telegram dizendo "quando alguém mandar mensagem para meu bot, POST nessa URL":
   ```
   POST https://api.telegram.org/bot{TOKEN}/setWebhook
   Body: { "url": "https://meusite.com/api/telegram/webhook/{TOKEN}" }
   ```

3. **Receber mensagens:** O Telegram chama `POST /api/telegram/webhook/{TOKEN}` com um objeto `Update`:
   ```json
   {
     "update_id": 123,
     "message": {
       "chat": { "id": 987654321, "type": "private", "first_name": "João" },
       "from": { "id": 987654321, "first_name": "João", "is_bot": false },
       "text": "Olá!"
     }
   }
   ```

4. **Enviar resposta:** Chamada HTTP direta para o Telegram:
   ```
   POST https://api.telegram.org/bot{TOKEN}/sendMessage
   Body: { "chat_id": 987654321, "text": "Olá! Como posso ajudar?" }
   ```

O `chat.id` do Telegram é o equivalente ao número de telefone do WhatsApp — é o identificador permanente do usuário.

---

## Comparação de fluxos

### WhatsApp (hoje)

```
1. Usuário manda msg no WhatsApp
2. Evolution API recebe
3. Evolution API → POST /api/whatsapp/webhook (com evento MESSAGES_UPSERT)
4. Nosso backend:
   - Busca WhatsappInstancia pelo instance_name
   - Cria/retoma Atendimento
   - Executa agente
   - POST evolution-api:8080/message/sendText/{instance} → usuário recebe
```

### Telegram (novo)

```
1. Usuário manda msg no bot Telegram
2. Telegram API → POST /api/telegram/webhook/{bot_token}
3. Nosso backend:
   - Busca TelegramInstancia pelo bot_token
   - Cria/retoma Atendimento (com canal=TELEGRAM)
   - Executa agente
   - POST api.telegram.org/bot{TOKEN}/sendMessage → usuário recebe
```

A lógica de atendimento, agente, SSE e banco é idêntica. Só muda quem "entrega" e quem "envia" as mensagens.

---

## Configuração dos Bots Telegram vs WhatsApp

A configuração do Telegram é intencionalmente diferente do WhatsApp:

| | WhatsApp | Telegram |
|-|---------|---------|
| Uma instância = | Um número de telefone | Um bot (`@username`) |
| Múltiplos por tenant | Sim | Sim |
| Autenticação | QR code (sessão ativa) | Token estático (bot token) |
| Cria atendimentos | Sempre | **Configurável por bot** |
| Agente vinculado | Um por instância | Um por bot |

O ponto central da diferença: um tenant pode ter vários bots Telegram com papéis distintos:
- **Bot de atendimento** — `cria_atendimentos=True`, vinculado a um agente, gera fila
- **Bot de notificações** — `cria_atendimentos=False`, usado só para envio proativo, não gera fila

---

## Mudanças de Schema

### Nova tabela: `telegram_instancia`

```
telegram_instancia
├── id
├── bot_token          (String 200, UNIQUE — nunca exposto em respostas de API)
├── bot_username       (String 100, nullable — ex: @MeuBotTeste, preenchido no create)
├── webhook_configured (Boolean — True após setWebhook com sucesso)
├── status             (Enum: ATIVA | INATIVA)
├── cria_atendimentos  (Boolean, default True — se False, bot só recebe/envia, sem fila)
├── tenant_id          (FK → tenant)
└── agente_id          (FK → agente, nullable — agente que responde neste bot)
```

### Comportamento por bot

Quando chega uma mensagem num bot com `cria_atendimentos=False`:
- A mensagem é processada pelo agente vinculado (se houver)
- A resposta é enviada diretamente, sem criar `Atendimento` no banco
- O atendimento **não aparece** na fila de atendimentos
- Útil para bots de FAQ, notificações ou automações simples sem operador humano

Quando `cria_atendimentos=True` (padrão):
- Comportamento idêntico ao WhatsApp — cria `Atendimento`, aparece na fila, operador pode assumir

### Schemas Telegram

```python
class TelegramInstanciaCreate(BaseModel):
    bot_token: str
    agente_id: int | None = None
    cria_atendimentos: bool = True   # default: gera fila

class TelegramInstanciaPublic(BaseModel):
    id: int
    bot_username: str | None
    webhook_configured: bool
    status: TelegramBotStatus
    cria_atendimentos: bool
    tenant_id: int
    agente_id: int | None
    created_at: datetime
    updated_at: datetime
    # bot_token: omitido intencionalmente
```

### Mudanças em `atendimento`

```
atendimento (mudanças)
├── instancia_id        → torna-se NULLABLE (era NOT NULL)
│                         (NULL para atendimentos Telegram)
├── canal               → novo campo: 'WHATSAPP' | 'TELEGRAM' (default 'WHATSAPP')
└── telegram_instancia_id → novo FK nullable → telegram_instancia
```

Invariante garantido na app layer: exatamente um de `instancia_id` / `telegram_instancia_id` está preenchido.

Queries WhatsApp existentes que filtram `instancia_id == X` continuam corretas — atendimentos WhatsApp ainda têm `instancia_id` preenchido.

---

## Estrutura de Arquivos

```
src/docagent/telegram/
├── __init__.py
├── models.py          — TelegramInstancia, TelegramBotStatus enum
├── schemas.py         — TelegramInstanciaCreate/Public, TelegramUpdate/Message/Chat/User
├── client.py          — factory get_telegram_client(bot_token) → httpx.AsyncClient
├── services.py        — TelegramService: CRUD instâncias + webhook + enviar_texto
└── router.py          — CRUD /api/telegram/instancias + webhook /api/telegram/webhook/{token}

alembic/versions/
└── XXXX_add_telegram.py   — criação da tabela + mudanças em atendimento

src/docagent/atendimento/
├── models.py          — + CanalAtendimento enum, canal column, telegram_instancia_id FK
├── schemas.py         — + canal, telegram_instancia_id, instancia_id: int|None
└── services.py        — enviar_mensagem_operador channel-aware

frontend/src/
├── api/client.ts                          — + Canal type, TelegramInstancia, 4 novos endpoints
├── views/telegram/TelegramView.vue        — gerenciamento de bots (novo)
├── views/atendimento/AtendimentoView.vue  — canal badge WA/TG
└── router/index.ts                        — + rota /telegram
```

---

## Endpoints Novos

| Método | Endpoint | Auth | Descrição |
|--------|----------|------|-----------|
| GET | `/api/telegram/instancias` | JWT | Lista bots do tenant |
| POST | `/api/telegram/instancias` | JWT | Cria bot + registra webhook no Telegram |
| DELETE | `/api/telegram/instancias/{id}` | JWT | Remove bot + cancela webhook |
| POST | `/api/telegram/instancias/{id}/webhook/configurar` | JWT | Re-registra webhook manualmente |
| POST | `/api/telegram/webhook/{bot_token}` | público | Recebe Updates do Telegram |

O endpoint de webhook é **público** (sem JWT) — o próprio Telegram o chama. O `bot_token` no path serve como autenticação implícita (só o Telegram e nós sabemos o token).

---

## Segurança do Webhook

O token do bot Telegram (ex: `123456:ABCdefGHI...`) nunca é exposto em respostas de API — é write-only (análogo a uma senha). O webhook usa o token como path parameter ao invés de header porque:

1. É a forma padrão do Telegram (muitos projetos OSS usam esse padrão)
2. O token já é suficientemente secreto (64 caracteres alfanuméricos)
3. Telegram também suporta um header opcional `X-Telegram-Bot-Api-Secret-Token` para validação adicional — pode ser adicionado futuramente

---

## Frontend — TelegramView

A tela de gerenciamento de bots (`/telegram`) tem uma tabela por bot:

| Campo | Descrição |
|-------|-----------|
| @username | Nome do bot (preenchido automaticamente no create) |
| Agente | Dropdown para vincular agente |
| Cria atendimentos | Toggle on/off |
| Webhook | Ícone ✓/✗ + botão "Reconfigurar" |
| Status | ATIVA / INATIVA |
| Ações | Remover |

Modal "Novo Bot":
- Campo `bot_token` (password input — não fica visível após salvar)
- Seletor de agente (opcional)
- Toggle "Criar atendimentos" (default: ativado)

Diferença visual clara do WhatsApp: não há botão "Conectar" nem QR code — o bot está sempre disponível enquanto o token for válido.

---

## Frontend — Canal Badge

Na lista de atendimentos, cada card receberá um badge de canal:

```
● [João Silva]    [WA]  [Bot]
● [987654321]     [TG]  [Bot]  [URGENTE]
```

- `WA` = verde (`bg-green-100 text-green-700`)
- `TG` = azul (`bg-blue-100 text-blue-700`)

A tela de gerenciamento de Telegram (`/telegram`) espelha a de WhatsApp (`/whatsapp`) mas sem QR code (não há sessão a autenticar — só token).

---

## Testes (TDD)

```
tests/test_telegram/
├── __init__.py
├── conftest.py                  — fixtures: db_session, client, _criar_telegram_instancia
├── test_models.py               — validações de modelo
├── test_services.py             — TelegramService (mock httpx para api.telegram.org)
├── test_router.py               — CRUD endpoints
├── test_webhook.py              — 9 cenários de webhook
└── test_atendimento_canal.py    — regressão: operador responde pelo canal correto
```

### Cenários do webhook

1. Token desconhecido → retorna 200 (fire-and-forget)
2. Mensagem de grupo → ignorada
3. Remetente é bot → ignorado
4. Sem campo `text` → ignorado
5. Bot com `cria_atendimentos=False` → agente responde diretamente, sem criar Atendimento
6. Bot com `cria_atendimentos=True` → primeiro contato cria Atendimento com `canal=TELEGRAM`
7. Segundo contato → retoma atendimento existente
8. Status HUMANO → agente não é acionado
9. Status ATIVO → agente executa e envia resposta via `sendMessage`
10. Atendimento criado tem `telegram_instancia_id` preenchido e `instancia_id=NULL`

---

## Ordem de Implementação

```
1. Branch: fase-16
2. Migração Alembic
3. telegram/models.py + atendimento/models.py + tenant/models.py
4. telegram/schemas.py + telegram/client.py
5. 🔴 RED: tests/test_telegram/conftest.py + test_models.py
6. 🟢 GREEN: telegram/services.py
7. 🔴 RED: test_services.py + test_router.py
8. 🟢 GREEN: telegram/router.py (CRUD + webhook)
9. 🔴 RED: test_webhook.py
10. api.py → registrar router
11. atendimento/schemas.py + atendimento/services.py
12. 🔴 RED: test_atendimento_canal.py
13. 🟢 GREEN → regressão (380+ testes passando)
14. Frontend: client.ts → TelegramView.vue → AtendimentoView.vue → router
```

---

## Gotchas

- **Alembic batch_alter_table** — SQLite não suporta `ALTER COLUMN`. Usar `op.batch_alter_table` para tornar `instancia_id` nullable.
- **`_agent_cache` isolado por módulo** — o cache de agentes do `telegram/router.py` é um dict separado do `whatsapp/router.py`. Os conftest de teste limpam cada um.
- **`chat_id` é inteiro** — `atendimento.numero` é string; ao chamar `sendMessage`, converter `int(atendimento.numero)`.
- **Contato model é WhatsApp-only** — a tabela `contato` tem FK → `whatsapp_instancia`. Para atendimentos Telegram, `contato_id=NULL`. O botão "Adicionar Contato" no frontend é ocultado quando `canal === 'TELEGRAM'`.
- **Helpers de teste existentes** — `_criar_atendimento` nos conftest antigos não passam `canal`; o ORM default (`WHATSAPP`) garante que os testes existentes continuem passando sem alteração.
