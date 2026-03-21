# Fase 13 — Atendimento WhatsApp

## Objetivo

Adicionar uma camada de gestão de atendimentos ao canal WhatsApp. Cada número que enviar mensagem inicia uma sessão de atendimento rastreada. O operador pode visualizar as conversas em tempo real e assumir o controle manual quando necessário.

## Funcionalidades

- **Rastreamento automático**: toda mensagem recebida de um número não-grupo cria ou retoma um `Atendimento`
- **Status do atendimento**:
  - `ATIVO` — agente responde automaticamente
  - `HUMANO` — operador assumiu, agente não responde
  - `ENCERRADO` — conversa finalizada
- **Histórico de mensagens**: cada mensagem (do contato, do agente, do operador) é salva com origem identificada
- **Tempo real**: painel com SSE mostra novas mensagens instantaneamente
- **Handoff**: operador pode assumir e devolver ao agente a qualquer momento

## Arquitetura

### Novos modelos

```
Atendimento
├── numero          (phone sem @s.whatsapp.net)
├── nome_contato    (opcional)
├── instancia_id    (FK → whatsapp_instancia)
├── tenant_id       (FK → tenant)
├── status          (ATIVO | HUMANO | ENCERRADO)
└── mensagens       (→ MensagemAtendimento[])

MensagemAtendimento
├── atendimento_id  (FK → atendimento)
├── origem          (CONTATO | AGENTE | OPERADOR)
└── conteudo        (Text)
```

### Módulo `src/docagent/atendimento/`

| Arquivo | Responsabilidade |
|---------|-----------------|
| `models.py` | SQLAlchemy models |
| `schemas.py` | Pydantic schemas de API |
| `services.py` | Lógica de negócio (criar_ou_retomar, assumir, devolver, encerrar, enviar_mensagem_operador) |
| `router.py` | Endpoints REST + SSE |
| `sse.py` | `AtendimentoSseManager` — broadcast por `atendimento_id` |

### Endpoints REST

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/api/atendimentos` | Lista atendimentos do tenant |
| GET | `/api/atendimentos/{id}` | Detalhe com histórico de mensagens |
| POST | `/api/atendimentos/{id}/assumir` | Operador assume → HUMANO |
| POST | `/api/atendimentos/{id}/devolver` | Devolve ao agente → ATIVO |
| POST | `/api/atendimentos/{id}/encerrar` | Encerra → ENCERRADO |
| POST | `/api/atendimentos/{id}/mensagens` | Operador envia mensagem (só quando HUMANO) |
| GET | `/api/atendimentos/{id}/eventos` | SSE stream de novas mensagens |

### Webhook atualizado (`whatsapp/router.py`)

Função `_processar_mensagem_recebida`:
1. Ignora grupos (`@g.us`)
2. Faz upsert do `Atendimento` (busca ativo/humano por instancia+numero, cria se não existe)
3. Salva `MensagemAtendimento(CONTATO)`
4. Broadcast SSE da mensagem do contato
5. **Se HUMANO**: para aqui (agente não é acionado)
6. **Se ATIVO**: executa agente → salva `MensagemAtendimento(AGENTE)` → broadcast SSE → envia via Evolution API

### Frontend (`AtendimentoView.vue`)

Painel em duas colunas:
- **Esquerda**: lista de atendimentos não-encerrados (polling a cada 5s). Badge colorido por status.
- **Direita**: mensagens em bolhas de chat com SSE em tempo real.
  - CONTATO → esquerda / cinza
  - AGENTE → direita / azul
  - OPERADOR → direita / verde
- Botões contextuais: **Assumir** (se ATIVO), **Devolver ao Agente** (se HUMANO), **Encerrar**
- Input de mensagem visível apenas quando HUMANO

## Testes (TDD)

Todos os testes foram escritos antes da implementação.

| Arquivo | Testes |
|---------|--------|
| `test_sse.py` | 4 — subscribe, broadcast, unsubscribe, isolamento |
| `test_services.py` | 8 — criar_ou_retomar, salvar_mensagem, assumir, devolver, encerrar, operador-sem-humano |
| `test_router.py` | 8 — listar, isolamento tenant, detalhe, assumir, devolver, encerrar, enviar-operador, 400-sem-humano |
| `test_webhook.py` | 5 — grupo ignorado, cria atendimento, retoma existente, humano bloqueia agente, ativo salva resposta |

Total: **25 testes** — todos passando.

## Migration

```
alembic/versions/a1b2c3d4e5f6_add_atendimento.py
```

Tabelas: `atendimento` + `mensagem_atendimento`

```bash
uv run alembic upgrade head
```

## Como usar

1. Conectar uma instância WhatsApp (fase 12)
2. Acessar `/atendimentos` no frontend
3. Mandar mensagem pelo WhatsApp → aparece na lista
4. Clicar no atendimento → ver conversa em tempo real
5. Clicar **Assumir** → agente para de responder
6. Digitar resposta na UI → enviada via Evolution API
7. Clicar **Devolver ao Agente** → agente retoma
