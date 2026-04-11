# DocAgent / z3ndocs

Plataforma SaaS de agentes de IA para análise de documentos PDF e atendimento multicanal (WhatsApp e Telegram).
Construída em fases progressivas — cada fase adiciona um conceito fundamental sobre agentes, APIs e SaaS.

Tudo roda localmente com [Ollama](https://ollama.com). Sem APIs pagas obrigatórias.

---

## Visão Geral

O z3ndocs é uma plataforma multi-tenant onde operadores podem criar agentes de IA configuráveis, cada um com um conjunto de skills (ferramentas), documentos próprios e um papel (system prompt) definidos pelo operador. Os agentes podem buscar em documentos PDF indexados, pesquisar na web, atender clientes via WhatsApp e Telegram com handoff humano, e responder por voz (STT + TTS).

---

## Stack

| Camada | Tecnologia |
|---|---|
| LLM local | `qwen2.5:7b` via Ollama |
| Embeddings | `nomic-embed-text` via Ollama |
| Orquestração de agentes | LangGraph |
| RAG | LangChain + ChromaDB |
| Memória de conversa | Summarize node customizado + histórico persistido no banco |
| API | FastAPI + streaming SSE |
| Banco de dados | SQLAlchemy async (SQLite dev / PostgreSQL prod) |
| Auth | JWT (PyJWT) + argon2 (pwdlib) |
| Frontend | Vue 3 + Pinia + Vue Router + Tailwind CSS v4 |
| UI alternativa | Streamlit |
| Canal WhatsApp | Evolution API v2 (self-hosted) |
| Canal Telegram | Telegram Bot API (direto, sem intermediário) |
| STT | faster-whisper (local) + OpenAI Whisper (API) |
| TTS | Piper (local) + OpenAI TTS + ElevenLabs |
| Proxy reverso (prod) | Traefik v3 + Let's Encrypt ACME |
| Infraestrutura | Docker Compose + uv |
| Observabilidade | LangSmith (opcional) |

---

## Fases do Projeto

### Fase 1 — RAG Pipeline `[concluída]`
Pipeline de ingestão e busca semântica em documentos PDF.

- Carrega PDFs com `PyMuPDFLoader`
- Divide em chunks com `RecursiveCharacterTextSplitter`
- Gera embeddings com `nomic-embed-text` via Ollama
- Persiste no ChromaDB
- Responde perguntas com citações de página

### Fase 2 — Agente com Tools `[concluída]`
Agente ReAct com decisão dinâmica de ferramenta.

- RAG e web search como `Tools` do LangChain
- Grafo de estados com LangGraph (StateGraph + aresta condicional)
- Loop ReAct: Reason → Act → Observe → Repeat

### Fase 3 — Memória `[concluída]`
Contexto persistente ao longo da conversa.

- `summarize node` no LangGraph com `qwen2.5:7b`
- Mensagens recentes mantidas na íntegra
- Histórico antigo comprimido em resumo incremental

### Fase 4 — API e Observabilidade `[concluída]`
Empacotamento via FastAPI com streaming SSE.

- Endpoints REST: `/chat`, `/health`, `/session`, `/documents/upload`
- Streaming SSE em tempo real (step + answer + done)
- Integração com LangSmith para rastreamento
- Interface Streamlit + Docker Compose

### Fase 5 — BaseAgent + Services `[concluída]`
Arquitetura em camadas com injeção de dependência.

- `BaseAgent` abstrato com Template Method Pattern
- `ChatService` e `IngestService` desacoplados do HTTP
- `SessionManager` para histórico de conversa
- Dependências via FastAPI `Depends()`

### Fase 6 — Skills + Registry `[concluída]`
Sistema de skills plugável.

- `SKILL_REGISTRY`: mapa nome → instância de skill
- Cada skill tem `name`, `label`, `icon`, `description` e `as_tool()`
- `ConfigurableAgent` monta tools e system prompt dinamicamente
- `AgentConfig` define quais skills cada agente usa

### Fase 7 — Streamlit Atualizado `[concluída]`
Interface Streamlit com seleção de agente e upload inline.

- Dropdown de seleção de agente (cache de 60s)
- Upload de PDF com feedback de chunks indexados
- Spinner de loading antes do primeiro evento SSE

### Fase 8 — Auth + Multi-tenant SaaS `[concluída]`
Autenticação JWT e arquitetura multi-tenant.

- `Usuario`, `Tenant`, `Admin` no banco com SQLAlchemy async
- JWT dual: token de usuário (`sub: username`) e token de admin (`sub: admin:username`)
- Roles: `OWNER` (dono do tenant) e `MEMBER`
- Alembic para migrações de banco
- Endpoints: `/auth/login`, `/auth/me`, `/auth/change-password`, `/api/usuarios/`, `/api/tenants/`, `/api/admin/`

### Fase 9 — Planos e Assinaturas `[planejada]`
Modelo de negócio SaaS com planos, limites de uso e assinaturas por tenant.

### Fase 10 — Frontend Vue.js `[concluída]`
Interface web profissional substituindo o Streamlit como frontend principal.

- Vue 3 + Composition API + TypeScript
- Pinia para estado global (auth, chat, agentes)
- Vue Router com guards por role (`requiresAuth`, `requiresAdmin`)
- Axios com interceptors (Bearer token + redirect 401)
- Chat com streaming SSE via `fetch` + `ReadableStream`
- Upload de PDF inline
- Painel admin separado (`/sys-mgmt`)
- CRUD de agentes com seleção de skills

### Fase 11 — MCP: Skills Dinâmicas `[concluída]`
Integração com o Model Context Protocol para adicionar tools sem escrever código.

- Registro de servidores MCP no banco (transporte stdio)
- Descoberta de tools via `POST /api/mcp-servidores/{id}/descobrir-tools`
- Skills MCP selecionáveis no CRUD de agentes
- Runtime: subprocessos MCP gerenciados via `AsyncExitStack` durante o streaming

### Fase 12 — Integração WhatsApp `[concluída]`
Canal de atendimento via WhatsApp usando a Evolution API v2 (self-hosted).

- Modelo `WhatsappInstancia` com vínculo a um agente e a um tenant
- CRUD de instâncias com QR code via SSE em tempo real
- Webhook receptor de mensagens da Evolution API
- Envio de respostas do agente de volta ao WhatsApp
- Sessão de conversa por número de telefone (`whatsapp:{numero}`)

### Fase 13 — Atendimento WhatsApp (TDD) `[concluída]`
Camada de gestão de atendimentos com histórico persistido e handoff humano.

- Modelo `Atendimento` com máquina de estados: `ATIVO → HUMANO → ENCERRADO`
- `MensagemAtendimento` com origem: `CONTATO | AGENTE | OPERADOR`
- Webhook estendido: cria/retoma atendimento a cada mensagem recebida
- Quando `HUMANO`, agente não é acionado — operador assume o controle
- SSE por `atendimento_id` para mensagens em tempo real no frontend
- 25 testes TDD (SSE, services, router, webhook)

### Fase 14 — Tempo Real, Contatos e Otimizações `[concluída]`
Melhorias de UX, módulo de contatos e redução de latência do agente.

- **SSE tenant-level**: lista de atendimentos atualizada em push (sem polling)
- **Reconexão automática**: backoff exponencial 2s→30s com refetch ao reconectar
- **Módulo Contatos**: cadastro com auto-link retroativo a atendimentos
- **Keep model warm**: warmup do Ollama no startup elimina cold start
- **Thread pool**: `agent.run()` via `run_in_executor` libera o event loop

### Fase 15 — RAG por Agente e Documentos `[concluída]`
Documentos indexados por agente em vez de collection global.

- Upload de PDFs vinculado ao `agente_id`: `POST /api/agentes/{id}/documentos`
- `rag_search` usa a collection do agente em uso na conversa
- Interface de documentos na página de edição do agente

### Fase 16 — Telegram + UI Refatorada + Infra de Produção `[concluída]`
Segundo canal de atendimento, UI reorganizada e stack de produção completo.

**Telegram:**
- Integração direta com Telegram Bot API (sem intermediário)
- Múltiplos bots por tenant (`TelegramInstancia`) com flag `cria_atendimentos`
  - `True` → cria fila de atendimento com handoff humano
  - `False` → agente responde diretamente (modo bot simples)
- `TelegramAtendimentoService` canal-específico

**Separação de serviços de atendimento:**
- `WhatsappAtendimentoService` — `criar_ou_retomar`, `iniciar_conversa`, `enviar_mensagem_operador` via Evolution API
- `TelegramAtendimentoService` — idem para Telegram Bot API
- `AtendimentoService` (base) — `assumir`, `devolver`, `encerrar`, `listar(canal?)` — sem dependência de canal
- Normalização de números de telefone (strip de formatação) para evitar duplicatas

**UI refatorada:**
- Sidebar: "Atendimentos WA" (`/atendimentos`) e "Atendimentos TG" (`/atendimentos/telegram`) como views separadas
- `AtendimentoView.vue` recebe prop `canal` — listagem e SSE filtrados por canal
- `/configuracoes`: 4 abas — Perfil / WhatsApp / Telegram / Servidores MCP

**Infraestrutura de produção:**
- `docker-compose.prod.yml`: Traefik v3 + Let's Encrypt ACME, PostgreSQL, nginx SPA
- `docker-compose.prod.local.yml`: versão sem SSL para testes locais
- `compose/entrypoint.prod.sh`: `alembic upgrade head` em vez de `create_all`

### Fase 17 — Planos, Assinaturas & Billing `[concluída]`
Sistema de monetização com planos de uso, quotas por tenant e painel de faturamento.

- Modelo `Plano` com limites: `limite_agentes`, `limite_documentos`, `limite_sessoes`, `ciclo_dias`
- Modelo `Assinatura` com `AssinaturaService`: `get_by_tenant`, `criar`, `checar_quota`, `uso_atual`
- Dependency `require_quota` — bloqueia endpoints quando quota excedida
- CRUD de planos via painel admin (`/api/admin/planos`)
- Endpoints tenant: `GET /api/assinatura/me`, `GET /api/assinatura/me/uso`
- Frontend: `AdminAssinaturasView`, visualização de uso de quota
- Suite TDD completa (service + router + quota)

### Fase 17b — Pipeline Multi-Agente de Vagas `[concluída]`
Esteira de 4 agentes LangGraph para análise de currículo e busca de vagas.

- Pipeline assíncrono: `cv_analyzer → job_searcher → personalizer → registrar`
- `cv_analyzer`: LLM extrai perfil estruturado do currículo em PDF
- `job_searcher`: busca vagas em DuckDuckGo, Gupy, LinkedIn e Indeed
- `personalizer`: gera resumo e carta de apresentação personalizada por vaga
- Progresso via SSE (mesmo padrão do módulo de atendimento)
- Frontend: seção `/vagas` com upload de PDF e acompanhamento em tempo real

### Fase 18b — Provider `hf_local`: TurboQuant KV Cache Compression `[concluída]`
LLM local via HuggingFace Transformers com compressão de KV cache para contextos longos em GPUs com pouca VRAM.

- Provider `hf_local` no `llm_factory.py` — carrega modelos Qwen diretamente via Transformers
- `llm_hf.py`: singleton por `(model, device, bit_width)`, OOM retry em sequência descendente `[4→3→2]` bits
- Integração com **TurboQuant** (`turboquant-torch`) — compressão Walsh-Hadamard + Lloyd-Max (~5-6x menos VRAM)
- Graceful degradation: sem `torch` instalado o provider levanta `RuntimeError` com instrução de instalação
- Optional-deps `hf`: `uv sync --extra hf` instala torch, transformers, accelerate, langchain-huggingface
- `tools/benchmark.py`: script standalone que compara FP16 vs TQ-Nbit (latência, throughput, VRAM)
- 18 testes TDD com mocks de `sys.modules` (nenhuma dependência GPU no CI)

### Fase 18 — Áudio: STT + TTS `[concluída]`
Pipeline de voz completo integrado ao WhatsApp e Telegram.

**Infraestrutura de áudio:**
- Módulo `audio/` com `AudioConfig` por tenant + por agente (cascata: agente → tenant → defaults)
- CRUD de config via `GET/PUT /api/audio-config/default` e `GET/PUT/DELETE /api/agentes/{id}/audio-config`
- Frontend: `AudioConfigForm.vue` + tabs de Áudio em Configurações e no formulário do agente

**STT (Speech-to-Text):**
- `FasterWhisperSTT` — transcrição local via faster-whisper, modelo carregado como singleton, roda em thread pool
- `OpenAIWhisperSTT` — fallback via API OpenAI

**TTS (Text-to-Speech):**
- `PiperTTS` — síntese local via subprocesso `piper` + `ffmpeg` (WAV raw → OGG/OPUS)
- `OpenAITTS` — OpenAI Text-to-Speech API
- `ElevenLabsTTS` — ElevenLabs API

**Integração nos canais:**
- WhatsApp: mensagens de voz transcritas automaticamente pelo STT antes de chegar ao agente
- Telegram: suporte a `voice` e `audio`; resposta em `audio_apenas`, `texto_apenas` ou `audio_e_texto`

**Dockerfile (Sprint 8):**
- `ffmpeg` + `libgomp1` (OpenMP para faster-whisper) + `wget`
- Pré-download do modelo Whisper `base` e Piper `pt_BR-faber-medium` no build da imagem

**Testes:**
- 42 testes unitários com mocks (rápidos, sem dependências externas)
- 12 testes de integração `@pytest.mark.integration` com binários reais (rodar no container)

### Fase 19 — Persistência de Histórico de Chat `[concluída]`
Histórico de conversas persistido no banco de dados, sidebar de conversas no frontend e retomada de conversa entre sessões.

- Tabelas `conversa` + `mensagem_conversa` com migration Alembic
- `ConversaService`: criar, listar paginado, salvar mensagens, gerar título automático via LLM em background, arquivar/restaurar (soft delete)
- `POST /chat` aceita `conversa_id` opcional — retoma conversa existente carregando histórico do banco
- Evento SSE `meta` retorna `conversa_id` ao frontend no início de cada stream
- Endpoints REST: `GET/DELETE /api/chat/conversas`, `GET /api/chat/conversas/{id}`, `POST /api/chat/conversas/{id}/restaurar`
- **Sidebar de conversas** no ChatView com abas Conversas / Docs, agrupamento por data (Hoje / Ontem / Esta semana / Mais antigas), infinite scroll (20/página) e botão de arquivar
- Trocar de agente na aba Docs carrega automaticamente a conversa mais recente desse agente (ou limpa a tela para nova conversa)
- 14 testes TDD (ConversaService + chat router com histórico), 589 testes passando no total

---

## Requisitos

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- [Docker](https://www.docker.com) + Docker Compose
- [Ollama](https://ollama.com) com os modelos:

```bash
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

---

## Instalação e Uso

### Desenvolvimento (Docker Compose)

```bash
git clone https://github.com/JuanLadeira/docagent.git
cd docagent
cp .env.example .env  # ajuste as variáveis se necessário

docker compose up -d
docker compose logs -f api  # acompanhar logs
```

Serviços:
| Serviço | URL | Descrição |
|---------|-----|-----------|
| API | `http://localhost:8000` | FastAPI (docs em `/docs`) |
| Frontend | `http://localhost:5173` | Vue.js dev server |
| Streamlit | `http://localhost:8501` | UI alternativa |
| Evolution API | `http://localhost:8080` | Gateway WhatsApp |

### Produção local (teste do stack prod sem SSL)

Para validar o docker-compose de produção na sua máquina antes de subir em servidor:

```bash
cp .env.prod.example .env.prod.local
# edite .env.prod.local com suas senhas de teste

docker compose -f docker-compose.prod.local.yml --env-file .env.prod.local build
docker compose -f docker-compose.prod.local.yml --env-file .env.prod.local up -d
docker compose -f docker-compose.prod.local.yml --env-file .env.prod.local logs -f api
```

Serviços disponíveis:
| Serviço | URL | Descrição |
|---------|-----|-----------|
| Frontend | `http://localhost` (porta 80) | nginx servindo a SPA Vue |
| API | `http://localhost:8000` | FastAPI com PostgreSQL |
| Evolution API | `http://localhost:8080` | Gateway WhatsApp |

> **Nota:** O frontend em produção faz proxy das rotas `/api/`, `/auth/`, `/chat/` etc. para `http://api:8000` internamente. Acesse tudo pela porta 80.

Para limpar os volumes ao finalizar:
```bash
docker compose -f docker-compose.prod.local.yml --env-file .env.prod.local down -v
```

### Produção com Cloudflare Tunnel (recomendado para home server)

Ideal para rodar no próprio PC sem abrir portas no roteador, sem IP fixo e sem problema de CGNAT. O tunnel `cloudflared` abre uma conexão de saída para a Cloudflare — o tráfego do domínio chega pelo tunnel direto para o nginx do frontend, que já faz proxy das rotas `/api/` para a API internamente.

**Pré-requisito:** domínio com DNS gerenciado pela Cloudflare. O domínio oficial do projeto é **z3ndocs.uk** (registrado via Cloudflare Registrar — ~£5/ano).

**Passo 1 — Criar o tunnel no painel da Cloudflare:**
1. Acesse [one.dash.cloudflare.com](https://one.dash.cloudflare.com) → Zero Trust → Networks → Tunnels
2. Create a tunnel → tipo **Cloudflared** → nome `docagent`
3. Copie o token exibido (começa com `eyJ...`)
4. Configure as **Public Hostnames**:
   - `z3ndocs.uk` → `http://frontend:80`
   - `evolution.z3ndocs.uk` → `http://evolution-api:8080` *(opcional)*

**Passo 2 — Subir o stack:**

```bash
cp .env.cloudflare.example .env.cloudflare
# edite .env.cloudflare: DOMAIN, CLOUDFLARE_TUNNEL_TOKEN, SECRET_KEY, senhas

docker compose -f docker-compose.cloudflare.yml --env-file .env.cloudflare up -d
docker compose -f docker-compose.cloudflare.yml --env-file .env.cloudflare logs -f
```

Sem abrir porta no roteador. SSL gerenciado pela Cloudflare. Funciona de qualquer PC com Docker e Ollama rodando.

Para derrubar:
```bash
docker compose -f docker-compose.cloudflare.yml --env-file .env.cloudflare down
```

### Produção com Traefik (VPS / servidor com IP público)

```bash
cp .env.prod.example .env.prod
# preencha: DOMAIN, ACME_EMAIL, SECRET_KEY, senhas, etc.

docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

Requer:
- Domínio apontando para o IP do servidor (DNS)
- Portas 80 e 443 abertas no firewall
- Traefik emite o certificado SSL automaticamente via Let's Encrypt

### Localmente sem Docker

```bash
uv sync

# Rodar a API
uv run uvicorn docagent.api:app --reload --port 8000

# Rodar o frontend
cd frontend && npm install && npm run dev
```

---

## Testes

```bash
uv run pytest tests/ -v                                    # todos os testes (unitários)
uv run pytest tests/test_atendimento/ -v                   # atendimentos
uv run pytest tests/test_telegram/ -v                      # Telegram
uv run pytest tests/test_fase11/ -v                        # MCP
uv run pytest tests/test_fase8/ -v                         # auth + tenant
uv run pytest tests/test_audio/ -v                         # áudio (unitários + skip de integração)

# Testes de integração de áudio — requerem piper + ffmpeg (rodar dentro do container)
docker compose exec api uv run pytest tests/test_audio/test_pipeline_integration.py -v
```

---

## Configuração

### Dev (`.env`)

```env
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=qwen2.5:7b
EMBED_MODEL=nomic-embed-text
SECRET_KEY=troque-em-producao
ADMIN_DEFAULT_USERNAME=admin
ADMIN_DEFAULT_PASSWORD=admin
EVOLUTION_API_KEY=changeme
```

### Produção (`.env.prod.local` ou `.env.prod`)

Copie de `.env.prod.example` e preencha. As variáveis principais:

| Variável | Descrição |
|----------|-----------|
| `DOMAIN` | Domínio principal (ex: `meusite.com`) |
| `ACME_EMAIL` | E-mail para Let's Encrypt (só prod real) |
| `SECRET_KEY` | Chave JWT — gere com `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | Senha do banco DocAgent |
| `POSTGRES_EVOLUTION_PASSWORD` | Senha do banco Evolution API |
| `EVOLUTION_API_KEY` | Chave da Evolution API |
| `OLLAMA_BASE_URL` | URL do Ollama (ex: `http://host.docker.internal:11434`) |
| `PIPER_MODELS_DIR` | Diretório dos modelos Piper (padrão: `/app/models/piper`) |
| `HF_HOME` | Cache do Hugging Face / Whisper (padrão: `/app/models/huggingface`) |

---

## Estrutura do Projeto

```
docagent/
├── compose/
│   ├── prod/api/
│   │   ├── Dockerfile          # imagem prod (ffmpeg + Whisper + Piper pré-instalados)
│   │   └── entrypoint.sh       # prod: alembic upgrade head + seeds
│   ├── Dockerfile              # imagem dev (api + streamlit)
│   └── entrypoint.sh           # dev: create_all + seeds
├── frontend/
│   ├── src/
│   │   ├── api/                # Axios client + tipos TypeScript
│   │   ├── stores/             # Pinia (auth)
│   │   ├── router/             # Vue Router com guards
│   │   └── views/              # páginas (auth, chat, agentes, atendimento, admin, vagas)
│   │       ├── atendimento/    # AtendimentoView (prop canal), ContatoView
│   │       ├── agentes/        # AgentesView, AgenteFormView (com aba Áudio)
│   │       ├── user/           # SettingsView (abas: perfil/whatsapp/telegram/mcp/áudio)
│   │       ├── telegram/       # TelegramView
│   │       └── vagas/          # VagasView (pipeline multi-agente)
│   ├── Dockerfile              # dev (Vite)
│   ├── Dockerfile.prod         # prod (build + nginx)
│   └── nginx.conf              # SPA routing + proxy para API
├── src/docagent/
│   ├── api.py                  # assembly do FastAPI app
│   ├── base_agent.py           # BaseAgent abstrato (LangGraph)
│   ├── agente/                 # CRUD de agentes (DB)
│   ├── agents/                 # ConfigurableAgent + AgentRegistry
│   ├── skills/                 # SKILL_REGISTRY (rag_search, web_search)
│   ├── auth/                   # JWT, security, router
│   ├── usuario/                # model, service, router
│   ├── tenant/                 # model, service, router
│   ├── plano/                  # model, CRUD admin
│   ├── assinatura/             # model, service, router, require_quota dependency
│   ├── vagas/                  # pipeline multi-agente (cv_analyzer → job_searcher → personalizer)
│   ├── audio/                  # STT + TTS — models, schemas, services, router, providers
│   │   ├── stt/                # FasterWhisperSTT, OpenAIWhisperSTT
│   │   └── tts/                # PiperTTS, OpenAITTS, ElevenLabsTTS
│   ├── conversa/               # histórico de chat — models, schemas, services, router
│   ├── agent/
│   │   ├── llm_factory.py      # factory multi-provider (ollama, openai, groq, anthropic, gemini, hf_local)
│   │   └── llm_hf.py           # provider hf_local — TurboQuant KV cache compression
│   ├── mcp_server/             # registro MCP, descoberta de tools
│   ├── whatsapp/               # instâncias WA, webhook, Evolution API client
│   │   └── atendimento_service.py  # WhatsappAtendimentoService
│   ├── telegram/               # instâncias TG, webhook, Telegram Bot API client
│   │   └── atendimento_service.py  # TelegramAtendimentoService
│   └── atendimento/            # AtendimentoService (base), models, router, SSE
├── tests/
│   ├── test_atendimento/       # services, router, SSE, webhook WA
│   ├── test_telegram/          # models, services, router, webhook TG
│   ├── test_fase17/            # AssinaturaService, quota, billing router
│   ├── test_audio/             # 42 testes unitários + 12 de integração (piper/whisper)
│   ├── test_llm_hf/            # 18 testes TDD — provider hf_local com mocks de sys.modules
│   └── test_historico/         # 14 testes TDD — ConversaService + chat router com histórico
├── tools/
│   └── benchmark.py            # benchmark FP16 vs TQ-Nbit (latência, throughput, VRAM)
├── alembic/                    # migrações de banco
├── docs/
│   ├── raw/                    # specs imutáveis por fase
│   └── wiki/                   # LLM Wiki — estado atual, log, gotchas, decisões
├── docker-compose.yml              # desenvolvimento
├── docker-compose.prod.yml         # produção (Traefik + SSL — VPS)
├── docker-compose.prod.local.yml   # teste local do stack prod (sem SSL)
├── docker-compose.cloudflare.yml   # produção via Cloudflare Tunnel (home server)
├── .env.example                    # template dev
├── .env.prod.example               # template produção Traefik
└── .env.cloudflare.example         # template produção Cloudflare Tunnel
```

---

## API — Principais Endpoints

| Método | Path | Descrição |
|--------|------|-----------|
| POST | `/auth/login` | Login (form data) → JWT |
| GET | `/api/usuarios/me` | Dados do usuário autenticado |
| POST | `/chat` | Chat SSE com agente |
| GET | `/api/agentes/` | CRUD de agentes |
| POST | `/api/agentes/{id}/documentos` | Upload PDF vinculado ao agente |
| GET | `/api/agentes/{id}/audio-config` | Config de áudio do agente |
| PUT | `/api/agentes/{id}/audio-config` | Atualizar config de áudio do agente |
| GET | `/api/audio-config/default` | Config de áudio padrão do tenant |
| PUT | `/api/audio-config/default` | Atualizar config de áudio padrão |
| GET | `/api/mcp-servidores` | CRUD de servidores MCP |
| GET | `/api/whatsapp/instancias` | CRUD de instâncias WhatsApp |
| POST | `/api/whatsapp/webhook` | Receptor de eventos da Evolution API |
| GET | `/api/whatsapp/instancias/{id}/eventos` | SSE — QR code e status |
| GET | `/api/telegram/instancias` | CRUD de bots Telegram |
| POST | `/api/telegram/webhook/{token}` | Receptor de updates do Telegram |
| GET | `/api/atendimentos?canal=WHATSAPP\|TELEGRAM` | Lista atendimentos (filtro por canal) |
| GET | `/api/atendimentos/eventos` | SSE — atualizações de lista em tempo real |
| POST | `/api/atendimentos/{id}/assumir` | Operador assume o atendimento |
| POST | `/api/atendimentos/{id}/devolver` | Devolve ao agente |
| POST | `/api/atendimentos/{id}/encerrar` | Encerra atendimento |
| GET | `/api/atendimentos/contatos` | CRUD de contatos |
| GET | `/api/chat/conversas` | Lista conversas do usuário (paginada) |
| GET | `/api/chat/conversas/{id}` | Conversa completa com mensagens |
| DELETE | `/api/chat/conversas/{id}` | Arquivar conversa (soft delete) |
| POST | `/api/chat/conversas/{id}/restaurar` | Restaurar conversa arquivada |
| GET | `/api/assinatura/me` | Assinatura e plano do tenant |
| GET | `/api/assinatura/me/uso` | Uso atual vs limites do plano |
| POST | `/api/vagas/pipeline` | Inicia pipeline de análise de currículo |
| GET | `/api/vagas/pipeline/{id}/eventos` | SSE — progresso do pipeline de vagas |
| GET | `/health` | Health check |

Documentação interativa disponível em `http://localhost:8000/docs`.
