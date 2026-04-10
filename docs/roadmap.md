# Roadmap — DocAgent / z3ndocs

> Atualizado em 2026-04-03. Estado atual: Fase 17 em andamento (planos/assinaturas/quotas).

---

## Estado atual

| Área | Status |
|------|--------|
| RAG + LangGraph + Memória | ✅ Completo |
| Auth JWT + Multi-tenant | ✅ Completo |
| Frontend Vue 3 | ✅ Completo |
| WhatsApp (Evolution API) | ✅ Completo |
| Telegram (Bot API) | ✅ Completo |
| Atendimento SSE real-time | ✅ Completo |
| MCP skills dinâmicas | ✅ Completo |
| Multi-LLM por tenant | ✅ Completo |
| Planos + Assinaturas + Quotas | 🟡 Fase 17 em andamento |
| Stripe / billing real | ❌ |
| Áudio STT + TTS | ❌ |
| Histórico de chat persistido | ❌ |
| Fine-tuning pipeline | ❌ |
| Segurança & Rate Limiting | ❌ |
| Analytics & Observabilidade | ❌ |
| Escalabilidade (Redis + Celery) | ❌ |
| E-mail + n8n | ❌ |
| PWA + Push Notifications | ❌ |

---

## Fases planejadas

| Fase | Tema | Design Doc | Prioridade |
|------|------|------------|------------|
| 17 | Planos, Assinaturas & Billing (Stripe) | [fase17-planos-assinaturas.md](fase17-planos-assinaturas.md) | 🔴 Agora |
| 18 | Mensagens de Áudio (STT + TTS) | [fase18-audio.md](fase18-audio.md) | 🔴 Próximo |
| 19 | Persistência de Histórico de Chat | [fase19-historico-chat.md](fase19-historico-chat.md) | 🟠 Alta |
| 20 | Fine-Tuning Pipeline | [fase20-finetuning.md](fase20-finetuning.md) | 🟠 Alta |
| 21 | Segurança & Rate Limiting | [fase21-seguranca.md](fase21-seguranca.md) | 🟠 Alta |
| 22 | Analytics & Observabilidade | [fase22-analytics.md](fase22-analytics.md) | 🟡 Média |
| 23 | Escalabilidade (Redis + Celery) | [fase23-escalabilidade.md](fase23-escalabilidade.md) | 🟡 Média |
| 24 | Canal E-mail & Integrações n8n | [fase24-email-n8n.md](fase24-email-n8n.md) | 🟢 Baixa |
| 25 | Mobile App (PWA + Push) | [fase25-pwa.md](fase25-pwa.md) | 🟢 Baixa |

---

## Resumo de cada fase

### Fase 17 — Planos, Assinaturas & Billing
Stripe SDK, webhooks de pagamento, renovação automática, grace period pós-vencimento, emails transacionais (Resend), dashboard admin de faturas. Fecha o ciclo de monetização do SaaS.

### Fase 18 — Mensagens de Áudio (STT + TTS)
Receber áudio (WhatsApp + Telegram), transcrever com faster-whisper (local) ou OpenAI Whisper (API), responder com voz via Piper TTS (local), OpenAI TTS ou ElevenLabs. Configurável por agente com fallback para padrão do tenant. Modo de resposta: `audio_apenas | texto_apenas | audio_e_texto`.

### Fase 19 — Persistência de Histórico de Chat
Tabelas `conversa` + `mensagem_conversa`. SessionManager migra de dict em memória para banco. Endpoints de listagem/retomada de conversas. Sidebar de histórico no ChatView (similar ao ChatGPT). Geração automática de título via LLM.

### Fase 20 — Fine-Tuning Pipeline
Dataset de treinamento coletado automaticamente dos atendimentos (curadoria humana antes de usar). Fine-tuning com Unsloth/QLoRA rodando localmente. Exportação para GGUF → Ollama. Modelo customizado disponível como opção de LLM no agente. SSE de log de treino em tempo real.

### Fase 21 — Segurança & Rate Limiting
`slowapi` nos endpoints críticos. Fernet para criptografar secrets no banco (`llm_api_key`, `elevenlabs_api_key`, `bot_token`). TOTP 2FA para admin. Tabela `audit_log` de ações administrativas. Validação de origem dos webhooks WhatsApp/Telegram.

### Fase 22 — Analytics & Observabilidade
Tabela `evento_analytics` com fire-and-forget em todos os pontos chave. Dashboard com gráficos de uso (Chart.js), top agentes, SLA de atendimento, taxa de resolução pelo agente. Logging estruturado (structlog JSON). Endpoint `/metrics` Prometheus. Health check detalhado em `/health`.

### Fase 23 — Escalabilidade
SessionManager → Redis (TTL automático). SSE → Redis Pub/Sub (funciona com múltiplas réplicas). `_agent_cache` → TTLCache com LRU. Celery + Redis para tarefas longas (fine-tuning, ingestão de PDF, emails, crons). Novos serviços Docker: `redis`, `celery-worker`, `celery-beat`.

### Fase 24 — Canal E-mail & Integrações n8n
E-mail como terceiro canal via Mailgun (inbound parsing → atendimento → agente → reply no thread). Sistema de webhooks de saída configurável por tenant (n8n, Zapier, etc.). Templates de workflow n8n pré-documentados. Badge `EM` na fila unificada de atendimentos.

### Fase 25 — Mobile App (PWA)
`vite-plugin-pwa` + service worker + Web App Manifest. Push notifications (Web Push API + VAPID) para novos atendimentos e urgências. Instalável no Android/iOS. Offline: lista de atendimentos cacheada. Instrução específica para iOS (adicionar à tela inicial primeiro).

---

## Gotchas técnicos a não esquecer

- `tests/confttest.py` tem typo — deveria ser `conftest.py` (afeta descoberta de fixtures globais)
- `_agent_cache` no chat router cresce sem limite — adicionar LRU antes de colocar em produção com carga
- `llm_api_key` em plaintext no banco — criptografar (Fase 21) antes de go-live real
- Alembic: sempre usar `batch_alter_table` para mudanças em colunas existentes (SQLite não suporta `ALTER COLUMN`)
- SSE managers não limpam conexões mortas — adicionar heartbeat + cleanup periódico (Fase 23)
- Rate limiting com múltiplos workers: `slowapi` usa memória local — usar backend Redis quando escalar (Fase 23)
