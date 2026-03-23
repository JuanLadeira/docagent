# DocAgent

Plataforma SaaS de agentes de IA para análise de documentos PDF e pesquisa na web.
Construída em fases progressivas — cada fase adiciona um conceito fundamental sobre agentes, APIs e SaaS.

Tudo roda localmente com [Ollama](https://ollama.com). Sem APIs pagas.

---

## Visão Geral

O DocAgent é uma plataforma multi-tenant onde usuários podem conversar com agentes de IA configuráveis, cada um com um conjunto de skills (ferramentas) e um papel (system prompt) definidos pelo operador. Os agentes podem buscar em documentos PDF indexados, pesquisar na web, e atender clientes via WhatsApp com handoff humano.

---

## Stack

| Camada | Tecnologia |
|---|---|
| LLM local | `qwen2.5:7b` via Ollama |
| Embeddings | `nomic-embed-text` via Ollama |
| Orquestração de agentes | LangGraph |
| RAG | LangChain + ChromaDB |
| Memória de conversa | Summarize node customizado |
| API | FastAPI + streaming SSE |
| Banco de dados | SQLAlchemy async (SQLite dev / PostgreSQL prod) |
| Auth | JWT (PyJWT) + argon2 (pwdlib) |
| Frontend | Vue 3 + Pinia + Vue Router + Tailwind CSS v4 |
| UI alternativa | Streamlit |
| Canal WhatsApp | Evolution API v2 (self-hosted) |
| Banco relacional | PostgreSQL (Evolution API) / SQLite (DocAgent dev) |
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
- Seleção de agente na sidebar
- Painel admin separado (`/sys-mgmt`)
- Gerenciamento de agentes (CRUD com seleção de skills)

### Fase 11 — MCP: Skills Dinâmicas `[planejada]`
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

### Fase 12b — Evolution API v2 `[concluída]`
Migração para a versão 2.3.7 da Evolution API (quebra de compatibilidade com v1).

- Dockerfile local da Evolution API v2 com build parametrizado
- PostgreSQL como banco de persistência da Evolution API
- Adaptação do webhook, criação de instância e envio de mensagem para a nova API

### Fase 13 — Atendimento WhatsApp (TDD) `[concluída]`
Camada de gestão de atendimentos com histórico persistido e handoff humano.

- Modelo `Atendimento` com máquina de estados: `ATIVO → HUMANO → ENCERRADO`
- `MensagemAtendimento` com origem: `CONTATO | AGENTE | OPERADOR`
- Webhook estendido: cria/retoma atendimento a cada mensagem recebida
- Quando `HUMANO`, agente não é acionado — operador assume o controle
- SSE por `atendimento_id` para mensagens em tempo real no frontend
- Painel Vue.js com bolhas de chat, badges de status e botões de handoff
- 25 testes TDD (SSE, services, router, webhook)

### Fase 14 — Tempo Real, Contatos e Otimizações `[concluída]`
Melhorias de UX, módulo de contatos e redução de latência do agente.

- **SSE tenant-level**: lista de atendimentos atualizada em push (sem polling)
- **Reconexão automática**: backoff exponencial 2s→30s com refetch ao reconectar
- **Banner de status**: indica "Conectando..." / "Reconectando..." na lista
- **Módulo Contatos**: cadastro de contatos com auto-link retroativo a atendimentos
- **ContatoView / ContatoDetalheView**: lista com busca e histórico por contato
- **Keep model warm**: warmup do Ollama no startup elimina cold start
- **Thread pool**: `agent.run()` via `run_in_executor` libera o event loop
- **Agent cache**: `ConfigurableAgent` cacheado por chave de configuração

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

### Com Docker Compose (recomendado)

```bash
git clone https://github.com/JuanLadeira/docagent.git
cd docagent
cp .env.example .env  # ajuste as variáveis

docker compose up -d
```

Serviços:
- **API**: `http://localhost:8000` — FastAPI + docs em `/docs`
- **Frontend**: `http://localhost:5173` — Vue.js
- **Streamlit**: `http://localhost:8501` — UI alternativa
- **Evolution API**: `http://localhost:8080` — gateway WhatsApp
- **PostgreSQL**: porta 5432 (interno, usado pela Evolution API)

O container da API cria as tabelas e o usuário padrão automaticamente no primeiro boot.

### Localmente (sem Docker)

```bash
uv sync

# Ingerir PDFs
uv run python -m docagent.ingest

# Rodar a API
uv run uvicorn docagent.api:app --reload --port 8000

# Rodar o frontend
cd frontend && npm install && npm run dev

# Rodar o Streamlit
uv run streamlit run src/docagent/ui.py
```

---

## Configuração

Crie um `.env` na raiz com:

```env
# LLM
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=qwen2.5:7b
EMBED_MODEL=nomic-embed-text
CHROMA_PATH=./data/chroma_db

# Banco de dados
DOCAGENT_DB_URL=sqlite+aiosqlite:///./docagent.db

# Auth
SECRET_KEY=troque-em-producao
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Usuário padrão (criado no primeiro boot)
ADMIN_DEFAULT_USERNAME=admin
ADMIN_DEFAULT_PASSWORD=admin

# Evolution API (WhatsApp)
EVOLUTION_API_KEY=changeme

# Observabilidade (opcional)
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=docagent
```

---

## Estrutura do Projeto

```
docagent/
├── compose/
│   ├── Dockerfile          # imagem Python (api + streamlit)
│   └── entrypoint.sh       # cria tabelas e usuário padrão no boot
├── data/
│   ├── pdfs/               # PDFs para ingestão (ignorado pelo git)
│   └── chroma_db/          # vector store persistido (ignorado pelo git)
├── docs/                   # design docs por fase
├── frontend/               # Vue.js SPA
│   ├── src/
│   │   ├── api/            # Axios client + tipos TypeScript
│   │   ├── stores/         # Pinia (auth, chat, agentes)
│   │   ├── router/         # Vue Router com guards
│   │   └── views/          # páginas (auth, chat, agentes, admin, user)
│   ├── Dockerfile
│   └── vite.config.ts
├── src/docagent/
│   ├── api.py              # assembly do FastAPI app
│   ├── base_agent.py       # BaseAgent abstrato (LangGraph)
│   ├── database.py         # SQLAlchemy async setup
│   ├── settings.py         # configurações via env vars
│   ├── session.py          # SessionManager (histórico de conversa)
│   ├── memory.py           # lógica de summarize
│   ├── ingest.py           # pipeline de ingestão de PDFs
│   ├── ui.py               # interface Streamlit
│   ├── agente/             # CRUD de agentes (DB)
│   ├── agents/             # ConfigurableAgent + AgentRegistry
│   ├── skills/             # SKILL_REGISTRY (rag_search, web_search)
│   ├── routers/            # chat, agents, documents
│   ├── services/           # ChatService, IngestService
│   ├── schemas/            # Pydantic schemas
│   ├── auth/               # JWT, security, router
│   ├── usuario/            # model, service, router
│   ├── tenant/             # model, service, router
│   ├── admin/              # model, router (admin separado)
│   ├── whatsapp/           # instâncias, webhook, cliente Evolution API
│   └── atendimento/        # models, services, router, SSE, schemas
├── tests/
├── alembic/                # migrações de banco
├── docker-compose.yml
└── pyproject.toml
```

---

## API — Principais Endpoints

| Método | Path | Descrição |
|--------|------|-----------|
| POST | `/auth/login` | Login (form data) → JWT |
| GET | `/auth/me` | Dados do usuário autenticado |
| POST | `/chat` | Chat SSE com agente |
| GET | `/agents` | Lista agentes ativos |
| POST | `/documents/upload` | Indexa PDF no ChromaDB |
| GET | `/api/agentes/` | CRUD de agentes |
| GET | `/api/usuarios/` | CRUD de usuários |
| GET | `/api/admin/tenants` | Painel admin — tenants |
| GET | `/api/whatsapp/instancias` | CRUD de instâncias WhatsApp |
| GET | `/api/whatsapp/instancias/{id}/eventos` | SSE — QR code e status de conexão |
| POST | `/api/whatsapp/webhook` | Receptor de eventos da Evolution API |
| GET | `/api/atendimentos` | Lista atendimentos do tenant |
| GET | `/api/atendimentos/eventos` | SSE — atualizações de lista em tempo real |
| POST | `/api/atendimentos/{id}/assumir` | Operador assume o atendimento |
| POST | `/api/atendimentos/{id}/devolver` | Devolve ao agente |
| POST | `/api/atendimentos/{id}/encerrar` | Encerra atendimento |
| GET | `/api/atendimentos/contatos` | CRUD de contatos |
| GET | `/health` | Health check |

Documentação interativa disponível em `http://localhost:8000/docs`.

---

## Documentação de Design

Cada fase tem um documento detalhado em `docs/`:

| Arquivo | Conteúdo |
|---------|----------|
| `fase1-design.md` | RAG pipeline: chunks, embeddings, LCEL chain |
| `fase2-design.md` | Agente ReAct: StateGraph, nós, aresta condicional |
| `fase3-design.md` | Memória: summarize node, threshold, injeção de contexto |
| `fase4-design.md` | API FastAPI: SSE, streaming, Docker |
| `fase5-design.md` | BaseAgent + Services: template method, injeção de dependência |
| `fase6-design.md` | Skills + Registry: plugabilidade, ConfigurableAgent |
| `fase7-design.md` | Streamlit: agent selector, upload, spinner |
| `fase8-design.md` | Auth + multi-tenant: JWT, roles, Alembic |
| `fase9-design.md` | Planos e assinaturas (planejado) |
| `fase10-design.md` | Frontend Vue.js: Pinia, Router, SSE streaming |
| `fase11-design.md` | MCP: skills dinâmicas via Model Context Protocol (planejado) |
| `fase12-design.md` | Integração WhatsApp: Evolution API, webhook, SSE de QR code |
| `fase13-design.md` | Atendimento WhatsApp: máquina de estados, TDD, handoff humano |
| `fase14-design.md` | SSE tenant-level, módulo Contatos, otimizações de latência |
