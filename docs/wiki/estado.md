# Estado Atual — DocAgent / z3ndocs

> Última atualização: 2026-04-13

---

## Branch atual: `fase-23` — PR #28 aberto para main

**PR:** [JuanLadeira/docagent#28](https://github.com/JuanLadeira/docagent/pull/28)
**Status:** Testes passando (628 passed, 12 skipped). Aguardando merge.

---

## O que está na fase-23

### Fase 23 — Escalabilidade (Redis + Celery)

- [x] `redis_client.py` — factory `get_redis_client()` → `redis.asyncio.Redis` ou `None`
- [x] `chat/session.py` — `RedisSessionManager` (pickle + TTL 1h) + `InMemorySessionManager` como fallback
- [x] `chat/service.py` — interface 100% async: `astream()` + `delete_session_async()`
- [x] `atendimento/sse.py` — Redis Pub/Sub bridge pattern nos dois managers SSE
- [x] `chat/router.py`, `telegram/router.py`, `whatsapp/router.py` — `TTLCache(maxsize=100, ttl=1800)` + `asyncio.Lock`
- [x] `api.py` lifespan — injeta Redis nos managers SSE e `_session_manager`
- [x] `dependencies.py` — variável de módulo substituível no lifespan (sem `@lru_cache`)
- [x] `celery_app.py` — broker Redis DB1, backend DB2
- [x] `tasks/ingestao.py` — `ingerir_documento_task` com retry (3x, 30s)
- [x] `agente/router.py` — upload retorna `202 Accepted` + `task_id` quando Celery disponível
- [x] `docker-compose.yml` — serviço `redis:7-alpine` (dev)
- [x] `docker-compose.cloudflare.yml` — redis + celery-worker + celery-beat + `SKIP_MIGRATIONS=true`
- [x] `compose/prod/api/entrypoint.sh` — guard `SKIP_MIGRATIONS` resolve crash-loop dos containers Celery
- [x] Testes: `tests/test_escalabilidade/` com `fakeredis` (13 testes)
- [x] Regressão: 628 passando, 12 skipped (integração de áudio)

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
| 23 | Escalabilidade — Redis + Celery | fase-23 (PR #28) |

---

## Próximas Fases

| Fase | Tema | Spec |
|------|------|------|
| 20 | Fine-Tuning Pipeline | [raw/fase20](../raw/fase20-finetuning.md) |
| 22 | Analytics & Observabilidade | [raw/fase22](../raw/fase22-analytics.md) |
| 24 | Canal E-mail & Integrações n8n | [raw/fase24](../raw/fase24-email-n8n.md) |
| 24 | Canal E-mail & Integrações n8n | [raw/fase24](../raw/fase24-email-n8n.md) |
| 25 | Mobile App (PWA + Push) | [raw/fase25](../raw/fase25-pwa.md) |

---

## Infraestrutura em Produção

- **Domínio:** z3ndocs.uk (Cloudflare Registrar)
- **Túnel:** Cloudflare Tunnel → PC local
- **Compose prod:** `docker-compose.cloudflare.yml` + `.env.cloudflare`
- **Serviços ativos:** api (8000), frontend nginx, evolution-api, postgres (2x), redis, celery-worker, celery-beat, cloudflared
- **Build:** `uv run task prod-build` → `docker compose -f docker-compose.cloudflare.yml --env-file .env.cloudflare up --build -d`

---

## Banco de Dados

- **Dev:** SQLite via aiosqlite (`docagent.db`)
- **Prod:** PostgreSQL via asyncpg
- **Migrations:** Alembic em `alembic/versions/`
- **Convenção:** usar `batch_alter_table` para mudanças em colunas existentes (SQLite não suporta ALTER COLUMN)
