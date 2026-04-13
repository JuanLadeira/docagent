# Estado Atual — DocAgent / z3ndocs

> Última atualização: 2026-04-12

---

## Branch atual: `fase-21` — PR #27 aberto para main

**PR:** [JuanLadeira/docagent#27](https://github.com/JuanLadeira/docagent/pull/27)
**Status:** Testes passando (615 passed, 36 skipped). Aguardando merge.

---

## O que está na fase-21

### Fase 19 — Persistência de Histórico de Chat
- [x] `src/docagent/conversa/` — models (`Conversa`, `MensagemConversa`), schemas, services, router
- [x] `GET /api/chat/conversas` com paginação, filtro por agente e arquivadas
- [x] `POST /chat` enriquecido com `conversa_id` opcional (nova ou existente)
- [x] `frontend/src/views/chat/` — sidebar de conversas, paginação, arquivar/restaurar
- [x] Auto-seleção do primeiro agente ao montar `ChatView`
- [x] Gravação e reprodução de áudio no chat UI (Fase 19 UI)
- [x] Alembic: `l2m3n4o5p6q7_add_conversas.py`
- [x] Testes: `tests/test_historico/`

### Fase 21 — Segurança & Rate Limiting
- [x] **21a** — `slowapi` rate limiting (login 5/min, chat 20/min por tenant, webhooks 100/min) + CORS restrito
- [x] **21b** — `EncryptedString` Fernet: `bot_token`, `llm_api_key`, `elevenlabs_api_key`, `totp_secret`
- [x] **21c** — Audit log: tabela `audit_log` + `AuditService` + `GET /api/admin/audit-logs`
- [x] **21d** — 2FA TOTP para admin: setup, confirmação, login em dois fatores
- [x] **21e** — Validação de origem: header `apikey` (WhatsApp) e `X-Telegram-Bot-Api-Secret-Token` (Telegram)
- [x] **21f** — CORS (entregue junto com 21a)
- [x] Alembic: 4 migrations (`n4o5p6...`, `o5p6q7...`, `p6q7r8...`, `q7r8s9...`)
- [x] Testes: `tests/test_seguranca/` (40 testes)

### Fixes (durante Fase 21)
- [x] Áudio não reproduzia no painel: `<audio src>` sem auth → `fetch()` + `URL.createObjectURL`
- [x] SSE usava `id: Date.now()` → backend agora inclui `mensagem_id` real nos payloads
- [x] STT: modelo `"base"` → `"small"` + `condition_on_previous_text=False` + `initial_prompt` pt-BR
- [x] Pentest interno: 4 vulnerabilidades corrigidas (ver abaixo)

### Correções de segurança (pentest interno)
- [x] **CRÍTICA** `tenant/router.py`: 5 endpoints CRUD públicos removidos
- [x] **CRÍTICA** `usuario/router.py`: GET e PUT sem auth + DELETE sem check de tenant — corrigidos
- [x] **HIGH** `agente/documento_service.py`: IDOR no DELETE de documentos — corrigido
- [x] **HIGH** `atendimento/router.py`: path traversal no media endpoint — corrigido com `pathlib`

---

## Fases Completas

| Fase | Tema | Branch |
|------|------|--------|
| 1–7 | RAG, LangGraph, Memória, FastAPI, BaseAgent, Skills, Streamlit | main |
| 8 | Auth JWT + Multi-tenant + Alembic | main |
| 10 | Frontend Vue 3 | main |
| 11 | MCP skills dinâmicas | main |
| 12 | WhatsApp Evolution API | main |
| 13 | Atendimento WhatsApp | main |
| 14 | Tempo real + Contatos SSE | main |
| 15 | Documentos por agente | main |
| 16 | Telegram Bot | main |
| 17 | Planos + Assinaturas + Quotas | main |
| 17b | Pipeline de Vagas | main |
| 18 | Áudio STT + TTS (WhatsApp + Telegram) | main |
| 19 | Persistência de Histórico de Chat | fase-21 (PR #27) |
| 21 | Segurança & Rate Limiting + Pentest | fase-21 (PR #27) |

---

## Próximas Fases

| Fase | Tema | Spec |
|------|------|------|
| 20 | Fine-Tuning Pipeline | [raw/fase20](../raw/fase20-finetuning.md) |
| 22 | Analytics & Observabilidade | [raw/fase22](../raw/fase22-analytics.md) |
| 23 | Escalabilidade (Redis + Celery) | [raw/fase23](../raw/fase23-escalabilidade.md) |
| 24 | Canal E-mail & Integrações n8n | [raw/fase24](../raw/fase24-email-n8n.md) |
| 25 | Mobile App (PWA + Push) | [raw/fase25](../raw/fase25-pwa.md) |

---

## Infraestrutura em Produção

- **Domínio:** z3ndocs.uk (Cloudflare Registrar)
- **Túnel:** Cloudflare Tunnel → PC local
- **Compose prod:** `docker-compose.cloudflare.yml` + `.env.cloudflare`
- **Serviços ativos:** api (8000), frontend nginx, evolution-api, postgres (2x), cloudflared
- **Build:** `uv run task prod-build` → `docker compose -f docker-compose.cloudflare.yml --env-file .env.cloudflare up --build -d`

---

## Banco de Dados

- **Dev:** SQLite via aiosqlite (`docagent.db`)
- **Prod:** PostgreSQL via asyncpg
- **Migrations:** Alembic em `alembic/versions/`
- **Convenção:** usar `batch_alter_table` para mudanças em colunas existentes (SQLite não suporta ALTER COLUMN)
