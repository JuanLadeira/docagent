# Log — DocAgent

Histórico cronológico de sprints e marcos. Append-only.
Formato: `## [YYYY-MM-DD] tipo | descrição`

---

## [2026-04-13] fase | Fase 23 — Escalabilidade Redis + Celery + PR #28

- `redis_client.py`: factory `get_redis_client()` → asyncio Redis ou None
- `chat/session.py`: `RedisSessionManager` (pickle + TTL 1h); `InMemorySessionManager` como fallback; `SessionManager` alias
- `chat/service.py`: `astream()` async generator + `delete_session_async()` — interface 100% async
- `atendimento/sse.py`: Redis Pub/Sub bridge nos dois managers SSE (atendimento + lista)
- 3 routers (chat, telegram, whatsapp): `_agent_cache` → `TTLCache(maxsize=100, ttl=1800)` + `asyncio.Lock`
- `api.py` lifespan: injeta Redis nos managers e `_session_manager`
- `dependencies.py`: variável de módulo substituível (sem `@lru_cache`)
- `celery_app.py` + `tasks/ingestao.py`: task `ingerir_documento` com retry 3x; upload retorna 202
- `docker-compose.yml`: Redis dev (porta 6379)
- `docker-compose.cloudflare.yml`: redis + celery-worker + celery-beat + volume `redis_data`
- `entrypoint.sh`: guard `SKIP_MIGRATIONS=true` — resolve crash-loop dos containers Celery
- `pyproject.toml`: `redis[asyncio]`, `cachetools`, `celery[redis]`, `fakeredis` (dev)
- Testes: `tests/test_escalabilidade/` 13 testes com `fakeredis` + regressão 628 passando
- Fix: `test_duckduckgo_usa_queries_homeoffice_com_modalidade` — trocado `asyncio.get_event_loop().run_until_complete()` por `@pytest.mark.asyncio`
- Limpeza: removidos `tests/test_agent.py`, `test_doc_agent.py`, `test_tools.py` (módulos removidos, 23 testes em skip permanente)
- PR #28 aberto para main

---

## [2026-04-12] fase | Fase 21 — Segurança, Rate Limiting, Pentest + PR #27

- `rate_limit.py`: slowapi, rate limits em auth/chat/webhooks, CORS
- `crypto.py`: EncryptedString Fernet — bot_token, llm_api_key, elevenlabs_api_key, totp_secret
- `audit/`: AuditLog ORM, AuditService.registrar() silent, GET /api/admin/audit-logs
- `auth/totp.py`: TOTP 2FA para admin — setup, confirmar, desativar
- `admin/router.py`: fluxo login 2FA com temp_token (JWT 5min)
- `telegram/`: webhook_secret (21e), migration q7r8s9t0u1v2
- `whatsapp/`: validação header apikey (21e)
- 4 vulnerabilidades de pentest corrigidas (tenant CRUD público, usuario GET/PUT sem auth, IDOR docs, path traversal áudio)
- Fix reprodução de áudio: fetch+blob ao invés de `<audio src>` sem auth
- Fix SSE: inclui mensagem_id real do banco nos payloads
- Fix STT: modelo "base" → "small" + parâmetros de qualidade
- 40 testes em tests/test_seguranca/
- PR #27 aberto para main

---

## [2026-04-11] fase | Fase 19 — Persistência de Histórico de Chat

- `conversa/models.py`: Conversa, MensagemConversa
- `conversa/router.py`: LIST (paginado), GET, DELETE (arquivar), POST (restaurar)
- `POST /chat` enriquecido com conversa_id opcional
- Frontend: sidebar de conversas, paginação, arquivar/restaurar
- Auto-seleção primeiro agente ao montar ChatView
- Gravação de áudio no chat UI
- Migration l2m3n4o5p6q7_add_conversas.py
- Testes: tests/test_historico/

---

## [2026-04-10] wiki | Criação do LLM Wiki

Migração de `docs/*.md` (specs de planejamento) para `docs/raw/`.
Criação de `docs/wiki/` com estrutura: index, estado, gotchas, log, fases/, modulos/, decisoes/.
Conhecimento compilado das fases 1–18.

---

## [2026-04-10] sprint | Fase 18 Sprint 7 — Frontend Áudio

- Criado `frontend/src/api/audioClient.ts`
- Criado `frontend/src/components/AudioConfigForm.vue` (STT/TTS toggles, provider-specific fields, override por agente)
- `SettingsView.vue`: nova aba "Áudio" (owner only)
- `AgenteFormView.vue`: card "Configuração de Áudio" no modo edição
- Fix: import não utilizado `baseApi` em `audioClient.ts` quebrava `vue-tsc` no prod-build

---

## [2026-04-10] build | prod-build validado

`uv run task prod-build` passou com sucesso após fix do import.
137 módulos buildados. Stack completa subiu: api, frontend, evolution-api, postgres (x2), cloudflared.

---

## [2026-04-09] sprint | Fase 18 Sprint 6 — Telegram Audio

- `telegram/schemas.py`: adicionados `TelegramVoice`, `TelegramAudio`, campos `voice`/`audio` em `TelegramMessage`
- `telegram/router.py`: guard atualizado, helpers `_baixar_audio_telegram`, `_executar_agente_telegram`, `_enviar_resposta_telegram`
- Testes: `test_webhook_telegram_audio.py` — 5 testes passando
- Fix: `patch("asyncio.get_event_loop")` não funcionava → trocado por patch direto em `_executar_agente_telegram`
- Fix: `TelegramBotStatus.ATIVO` → `ATIVA`

---

## [2026-04-09] sprint | Fase 18 Sprint 5 — WhatsApp Audio

- `whatsapp/router.py`: detecção `audioMessage`, helpers `_baixar_midia_evolution`, `_executar_agente_whatsapp`, `_enviar_resposta_whatsapp`
- Testes: `test_webhook_whatsapp_audio.py` — 5 testes passando

---

## [2026-04-08] sprint | Fase 18 Sprints 1-4 — Backend Áudio

- `audio/models.py`: AudioConfig ORM, SttProvider, TtsProvider, ModoResposta
- `audio/services.py`: AudioService com resolver_config (cascata), transcrever, sintetizar
- `audio/stt/`: FasterWhisperSTT (singleton, asyncio.to_thread), OpenAIWhisperSTT
- `audio/tts/`: PiperTTS (subprocess + ffmpeg), OpenAITTS, ElevenLabsTTS
- `audio/router.py`: 5 endpoints CRUD
- Alembic: `k1l2m3n4o5p6_add_audio_config.py`
- `api.py`: router registrado
- Testes: conftest, test_audio_service, test_stt_providers, test_tts_providers, test_audio_router
- Fix: FK `agentes.id` → `agente.id` (tablename singular)
- Fix: `AudioConfig.__new__()` → `types.SimpleNamespace` para system defaults

---

## [2026-04-07] merge | Fase 17b mergeada para main

Pipeline de vagas (candidatos, CV, ranking, pipeline kanban) mergeado.
Branch `fase-17b` → `main`.

---

## [2026-04-03] sprint | Fase 17 — Planos + Assinaturas + Quotas + Admin Billing

- Modelos: `Plano`, `Assinatura` com campos `limite_agentes`, `ciclo_dias`
- `require_quota` dependency: enforcement em agentes e documentos
- Admin billing UI: `AdminPlanosView.vue`, `AdminAssinaturasView.vue`
- Schemas Alembic para merge de heads

---

## [2026-03-xx] sprint | Fases 1-16 (histórico consolidado)

Fases 1–16 implementadas incrementalmente. Ver `docs/raw/` para specs detalhadas de cada fase.
Destaques:
- Fase 8: Auth JWT dual (user/admin), multi-tenant, Alembic
- Fase 11: MCP via stdio com AsyncExitStack
- Fase 12: WhatsApp via Evolution API v2.3.7
- Fase 13: Atendimento com máquina de estados + SSE (25 testes TDD)
- Fase 16: Telegram Bot com webhook nativo
