# Fase 13 — Design: Atendimento WhatsApp (TDD)

## Contexto

Com a Fase 12 entregando o canal WhatsApp (envio/recebimento de mensagens via Evolution API), a Fase 13 adiciona a camada de gestão de atendimentos: cada número que envia mensagem gera uma sessão rastreada com status, histórico e controle manual pelo operador.

---

## Problema

A Fase 12 processava mensagens de forma stateless — o agente respondia, mas nada era persistido além da sessão de memória do LangGraph. Não havia como:

- Saber quantas conversas estavam ativas
- Ver o histórico de uma conversa
- Intervir manualmente em uma conversa (operador assumir)
- Diferenciar "bot respondendo" de "operador respondendo"

---

## Solução

Modelo `Atendimento` com máquina de estados simples + `MensagemAtendimento` para histórico persistido. O webhook existente é estendido para criar/retomar atendimentos e salvar cada mensagem.

### Máquina de estados

```
          mensagem recebida
               │
               ▼
     ┌─────────────────┐
     │      ATIVO      │◄─── devolver_ao_agente()
     │  (bot responde) │
     └────────┬────────┘
              │ assumir()
              ▼
     ┌─────────────────┐
     │     HUMANO      │
     │ (op. responde)  │
     └────────┬────────┘
              │ encerrar()
              ▼
     ┌─────────────────┐
     │   ENCERRADO     │
     │  (read-only)    │
     └─────────────────┘
```

**Regra central:** quando o status é `HUMANO`, o webhook salva a mensagem do contato mas **não aciona o agente**. O agente só é chamado quando `ATIVO`.

---

## Modelo de Dados

```python
class AtendimentoStatus(str, Enum):
    ATIVO = "ATIVO"
    HUMANO = "HUMANO"
    ENCERRADO = "ENCERRADO"

class MensagemOrigem(str, Enum):
    CONTATO = "CONTATO"
    AGENTE = "AGENTE"
    OPERADOR = "OPERADOR"

class Atendimento(Base):
    numero: str               # telefone sem @s.whatsapp.net
    nome_contato: str | None  # preenchido se contato cadastrado
    instancia_id: int         # FK → WhatsappInstancia
    tenant_id: int            # FK → Tenant
    status: AtendimentoStatus # ATIVO | HUMANO | ENCERRADO

class MensagemAtendimento(Base):
    atendimento_id: int       # FK → Atendimento
    origem: MensagemOrigem    # CONTATO | AGENTE | OPERADOR
    conteudo: str
    created_at: datetime
```

---

## Arquitetura do Módulo

```
src/docagent/atendimento/
├── models.py     — ORM: Atendimento, MensagemAtendimento
├── schemas.py    — Pydantic: AtendimentoPublic, AtendimentoDetalhe, MensagemPublic
├── services.py   — lógica: criar_ou_retomar, assumir, devolver, encerrar, enviar_mensagem_operador
├── router.py     — endpoints REST + SSE por atendimento_id
└── sse.py        — AtendimentoSseManager (filas por atendimento_id)
```

### `AtendimentoSseManager`

Dicionário `atendimento_id → set[asyncio.Queue]`. Cada conexão SSE do frontend cria uma fila. `broadcast(atendimento_id, event)` coloca o evento em todas as filas daquele atendimento. Isolamento por design: uma instância não recebe eventos de outra.

---

## Endpoints

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/api/atendimentos` | Lista atendimentos do tenant (filtrável por status) |
| `GET` | `/api/atendimentos/{id}` | Detalhe com histórico completo de mensagens |
| `POST` | `/api/atendimentos/{id}/assumir` | Muda status para HUMANO |
| `POST` | `/api/atendimentos/{id}/devolver` | Muda status para ATIVO |
| `POST` | `/api/atendimentos/{id}/encerrar` | Muda status para ENCERRADO |
| `POST` | `/api/atendimentos/{id}/mensagens` | Operador envia mensagem (requer status HUMANO) |
| `GET` | `/api/atendimentos/{id}/eventos` | SSE stream de novas mensagens |

---

## Fluxo do Webhook (estendido)

```
Evolution API → POST /api/whatsapp/webhook
     │
     ├─ Ignora grupos (@g.us)
     ├─ Busca WhatsappInstancia pelo instance_name
     ├─ criar_ou_retomar(instancia_id, numero)
     │       └─ SELECT ativo/humano → se não existe, cria ATIVO
     ├─ Salva MensagemAtendimento(CONTATO)
     ├─ Broadcast SSE: NOVA_MENSAGEM (contato)
     │
     ├─ [se HUMANO] → para aqui, agente não é acionado
     │
     └─ [se ATIVO]
           ├─ agent.run(conteudo, state)
           ├─ Salva MensagemAtendimento(AGENTE)
           ├─ Broadcast SSE: NOVA_MENSAGEM (agente)
           └─ Evolution API → envia resposta ao WhatsApp
```

---

## Frontend

Painel em duas colunas (`AtendimentoView.vue`):

**Esquerda — lista de atendimentos**
- Badge colorido: verde (ATIVO), laranja (HUMANO), cinza (ENCERRADO)
- Atualizado via polling a cada 5s (substituído por SSE na Fase 14)

**Direita — conversa**
- Bolhas de chat com SSE em tempo real
- CONTATO → esquerda / cinza
- AGENTE → direita / índigo
- OPERADOR → direita / verde
- Botões contextuais: **Assumir** (se ATIVO), **Devolver ao Agente** (se HUMANO), **Encerrar**
- Input de mensagem visível apenas quando HUMANO

---

## TDD

Todos os testes foram escritos antes da implementação (red → green → refactor).

| Arquivo | Testes | O que cobre |
|---------|--------|-------------|
| `test_sse.py` | 4 | subscribe, broadcast, unsubscribe, isolamento entre atendimentos |
| `test_services.py` | 8 | criar_ou_retomar, salvar_mensagem, assumir, devolver, encerrar, bloquear operador sem HUMANO |
| `test_router.py` | 8 | listar, isolamento tenant, detalhe, assumir, devolver, encerrar, enviar-operador, 400 sem HUMANO |
| `test_webhook.py` | 5 | grupo ignorado, cria atendimento, retoma existente, HUMANO bloqueia agente, ATIVO salva resposta |

**Total: 25 testes — todos passando.**

---

## Migration

`alembic/versions/a1b2c3d4e5f6_add_atendimento.py`

Cria tabelas `atendimento` e `mensagem_atendimento`.

```bash
uv run alembic upgrade head
```

---

## Arquivos Modificados/Criados

| Arquivo | Mudança |
|---------|---------|
| `src/docagent/atendimento/models.py` | Novos modelos: `Atendimento`, `MensagemAtendimento`, enums |
| `src/docagent/atendimento/schemas.py` | Schemas Pydantic de resposta |
| `src/docagent/atendimento/services.py` | Lógica de negócio do ciclo de vida |
| `src/docagent/atendimento/router.py` | REST endpoints + SSE por atendimento |
| `src/docagent/atendimento/sse.py` | `AtendimentoSseManager` |
| `src/docagent/whatsapp/router.py` | Webhook estendido com criação/retomada de atendimento |
| `src/docagent/api.py` | Registro do router de atendimentos |
| `alembic/versions/a1b2c3d4e5f6_add_atendimento.py` | Migration |
| `frontend/src/views/atendimento/AtendimentoView.vue` | Painel de atendimentos |
| `frontend/src/api/client.ts` | Tipos e funções SSE de atendimento |
| `frontend/src/router/index.ts` | Rota `/atendimentos` |
| `frontend/src/App.vue` | Item "Atendimentos" na nav |
| `tests/test_fase12/` | 25 testes TDD |

---

## Trade-offs

| Decisão | Alternativa considerada | Motivo escolhido |
|---------|------------------------|-----------------|
| `nome_contato` desnormalizado em `Atendimento` | JOIN com tabela de contatos | Exibição rápida sem JOIN; contatos eram opcionais nesta fase |
| SSE por `atendimento_id` | WebSocket | SSE é unidirecional (suficiente), mais simples de manter com proxies |
| Status como `str` Enum | `bool` `humano` flag | Extensível para futuros estados sem migration |
| Polling de 5s na lista | SSE tenant-level | Simplicidade; SSE na lista foi entregue na Fase 14 |
