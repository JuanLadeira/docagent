# Estado Atual — DocAgent / z3ndocs

> Última atualização: 2026-04-10

---

## Fase em andamento: 18 — Áudio STT + TTS

**Branch:** `fase-18`
**Sprint atual:** 7 (frontend) — concluído. Sprint 8 (regressão + Dockerfile) pendente.

### O que foi implementado na Fase 18

- [x] `src/docagent/audio/models.py` — AudioConfig ORM + enums
- [x] `src/docagent/audio/schemas.py` — AudioConfigPublic, AudioConfigUpdate
- [x] `src/docagent/audio/services.py` — AudioService (resolver_config, transcrever, sintetizar)
- [x] `src/docagent/audio/stt/faster_whisper.py` — singleton, asyncio.to_thread
- [x] `src/docagent/audio/stt/openai_whisper.py` — POST à API OpenAI
- [x] `src/docagent/audio/tts/piper.py` — subprocess + ffmpeg WAV→OGG
- [x] `src/docagent/audio/tts/openai_tts.py` — POST à API OpenAI
- [x] `src/docagent/audio/tts/elevenlabs.py` — POST à API ElevenLabs
- [x] `src/docagent/audio/router.py` — 5 endpoints GET/PUT/DELETE
- [x] `alembic/versions/k1l2m3n4o5p6_add_audio_config.py`
- [x] `src/docagent/whatsapp/router.py` — detecção e processamento de audioMessage
- [x] `src/docagent/telegram/router.py` — detecção de voice/audio + helpers
- [x] `src/docagent/telegram/schemas.py` — TelegramVoice, TelegramAudio adicionados
- [x] `frontend/src/api/audioClient.ts`
- [x] `frontend/src/components/AudioConfigForm.vue`
- [x] `frontend/src/views/user/SettingsView.vue` — aba "Áudio" adicionada
- [x] `frontend/src/views/agentes/AgenteFormView.vue` — card Áudio no modo edição
- [x] Testes: `tests/test_audio/` (conftest, service, stt, tts, router, whatsapp, telegram)

### Pendente na Fase 18

- [ ] Sprint 8: rodar suite completa de regressão (`uv run pytest tests/ -v`)
- [ ] Sprint 8: Dockerfile — `apt install ffmpeg`, pré-download modelos Piper e Whisper

---

## Fases Completas

| Fase | Tema | Branch mergeada |
|------|------|-----------------|
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

---

## Próximas Fases (em ordem de prioridade)

| Fase | Tema | Spec |
|------|------|------|
| 19 | Persistência de Histórico de Chat | [raw/fase19](../raw/fase19-historico-chat.md) |
| 20 | Fine-Tuning Pipeline | [raw/fase20](../raw/fase20-finetuning.md) |
| 21 | Segurança & Rate Limiting | [raw/fase21](../raw/fase21-seguranca.md) |
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
