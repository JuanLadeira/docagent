# CLAUDE.md — DocAgent

Plataforma SaaS multi-tenant de agentes de IA para análise de documentos e integração com WhatsApp.

> **Wiki do projeto:** [`docs/wiki/`](docs/wiki/index.md) — estado atual, módulos, decisões arquiteturais, gotchas acumulados.
> **Specs de planejamento:** [`docs/raw/`](docs/raw/) — design docs por fase (imutáveis).

---

## Como Rodar

**Sempre usar Docker Compose** — o projeto roda via containers:

```bash
docker compose up -d          # Iniciar todos os serviços
docker compose logs -f api    # Logs da API
docker compose restart api    # Reiniciar após mudanças no backend
```

**Serviços:**
| Serviço | Porta | Descrição |
|---------|-------|-----------|
| `api` | 8000 | FastAPI (docs em /docs) |
| `frontend` | 5173 | Vue 3 + Vite dev |
| `ui` | 8501 | Streamlit (alternativa) |
| `evolution-api` | 8080 | WhatsApp gateway |
| `postgres` | 5432 | Banco da Evolution API |

**Testes:**
```bash
uv run pytest tests/ -v
uv run pytest tests/test_fase11/ -v    # MCP
uv run pytest tests/test_atendimento/ -v
uv run pytest tests/test_fase8/ -v     # Auth + tenant
```

O `asyncio_mode = "strict"` está configurado em `pyproject.toml`. Usar `uv run pytest` (não `python -m pytest` diretamente, pois as dependências ficam no virtualenv do uv).

---

## Stack

- **Backend:** Python 3.11+, FastAPI, LangGraph, SQLAlchemy async, Alembic
- **LLM:** Ollama local (`qwen2.5:7b`), embeddings `nomic-embed-text`
- **RAG:** ChromaDB + LangChain
- **MCP:** `mcp` SDK + `langchain-mcp-adapters` (transporte stdio)
- **Frontend:** Vue 3 + TypeScript + Pinia + Vue Router + Tailwind CSS v4
- **Auth:** JWT (pyjwt) + Argon2 (pwdlib)
- **WhatsApp:** Evolution API v2.3.7 (self-hosted, PostgreSQL próprio)
- **Banco (dev):** SQLite via aiosqlite
- **Banco (prod):** PostgreSQL via asyncpg
- **Gerenciador de pacotes:** `uv`

---

## Estrutura do Backend (`src/docagent/`)

| Módulo | Responsabilidade |
|--------|-----------------|
| `api.py` | App FastAPI, registro de routers, lifespan |
| `base_agent.py` | BaseAgent abstrato (Template Method, LangGraph StateGraph) |
| `agent.py` | Agente legacy |
| `agents/` | `ConfigurableAgent` (monta tools+system prompt) + `AgentRegistry` |
| `skills/` | `SKILL_REGISTRY`: `rag_search`, `web_search` |
| `routers/chat.py` | POST /chat (SSE streaming), MCP AsyncExitStack lifecycle |
| `routers/agents.py` | GET /agents |
| `routers/documents.py` | POST /documents/upload |
| `services/chat_service.py` | Orquestra agente + sessão |
| `services/ingest_service.py` | Pipeline PDF |
| `auth/` | JWT, security, current_user dependency |
| `usuario/` | Modelo + CRUD de usuários |
| `tenant/` | Multi-tenancy |
| `agente/` | CRUD de agentes (skill_names, system_prompt) |
| `mcp_server/` | Registro MCP, descoberta de tools, runtime stdio |
| `whatsapp/` | Evolution API v2: instâncias, webhook, QR code WS |
| `atendimento/` | Atendimentos WhatsApp + SSE em tempo real + Contatos |
| `admin/` | Endpoints admin separados |
| `plano/` | Modelos de plano (Fase 9 — em andamento) |
| `assinatura/` | Assinaturas por tenant (Fase 9 — em andamento) |
| `memory.py` | Summarize node + trim messages |
| `session.py` | SessionManager (histórico de conversa) |
| `database.py` | SQLAlchemy async engine + session factory |
| `settings.py` | Config via env vars |

---

## Arquitetura do Agente (LangGraph)

```
POST /chat
  ├─ Carrega Agente do banco
  ├─ Separa skill_names: built-in vs mcp:*
  ├─ Se MCP: AsyncExitStack + carrega tools via stdio
  ├─ ConfigurableAgent(config, extra_tools=mcp_tools).build()
  └─ StreamingResponse com SSE

LangGraph StateGraph:
  START → agent_node → [should_continue?]
                          ├─ tools_node → agent_node  (loop ReAct)
                          └─ summarize_node → END

AgentState:
  ├─ messages: list[BaseMessage]
  └─ summary: str  (histórico comprimido)
```

**Skills MCP:** convenção `mcp:{server_id}:{tool_name}` em `Agente.skill_names`. Skills built-in sem prefixo: `rag_search`, `web_search`.

---

## Multi-Tenancy

```
Tenant
  ├─ Usuario (role: OWNER | MEMBER)
  ├─ Agente (skill_names, system_prompt)
  ├─ WhatsappInstancia (agente vinculado)
  ├─ Atendimento (número, status: ATIVO→HUMANO→ENCERRADO)
  └─ Contato (número, nome, email, notas)
```

**JWT dual:**
- User: `sub=username` → endpoints /chat, /api/*
- Admin: `sub=admin:username` → endpoints /sys-mgmt, /api/admin/*

---

## Fluxo WhatsApp

```
Webhook Evolution API → POST /api/whatsapp/webhook
  ├─ Cria Atendimento se não existir
  ├─ Cria/atualiza Contato
  ├─ Routing: agente automático vs handoff humano
  └─ Emite SSE para operadores do tenant

Atendimento: ATIVO → HUMANO → ENCERRADO
SSE: /api/atendimentos/{id}/sse  (conversa)
SSE: /api/atendimentos/lista/sse (lista de todos)
```

---

## Variáveis de Ambiente Relevantes

```env
OLLAMA_BASE_URL=http://ollama:11434   # ou http://host.docker.internal:11434
LLM_MODEL=qwen2.5:7b
EMBED_MODEL=nomic-embed-text
DOCAGENT_DB_URL=sqlite+aiosqlite:///./docagent.db  # dev
SECRET_KEY=troque-em-producao
EVOLUTION_API_URL=http://evolution-api:8080
EVOLUTION_API_KEY=changeme
WEBHOOK_BASE_URL=http://api:8000
FRONTEND_URL=http://localhost:5173
ADMIN_DEFAULT_USERNAME=admin
ADMIN_DEFAULT_PASSWORD=admin
```

---

## Fases Implementadas

| Fase | Status | Tema |
|------|--------|------|
| 1 | ✅ | RAG Pipeline (PDF → ChromaDB) |
| 2 | ✅ | Agente ReAct (LangGraph) |
| 3 | ✅ | Memória (summarize + trim) |
| 4 | ✅ | API FastAPI + Docker + Streamlit |
| 5 | ✅ | BaseAgent + Services (Template Method) |
| 6 | ✅ | Skills + SKILL_REGISTRY + ConfigurableAgent |
| 7 | ✅ | Streamlit atualizado |
| 8 | ✅ | Auth JWT + Multi-tenant + Alembic |
| 9 | 🟡 | **Planos e Assinaturas** (em andamento) |
| 10 | ✅ | Frontend Vue.js (Pinia, Router, CRUD agentes) |
| 11 | ✅ | MCP: skills dinâmicas via Model Context Protocol |
| 12 | ✅ | WhatsApp: Evolution API v2.3.7 |
| 13 | ✅ | Atendimento WhatsApp (máquina de estados, TDD) |
| 14 | ✅ | Tempo real + Contatos (SSE, reconexão) |

---

## Pendências / O Que Falta

### Fase 9 — Planos e Assinaturas
- Estrutura iniciada em `src/docagent/plano/` e `src/docagent/assinatura/` (untracked)
- Falta: services, endpoints CRUD, lógica de quotas, integração no /chat, frontend

### Testes
- `tests/confttest.py` — arquivo com typo (deveria ser `conftest.py`)
- `tests/test_fase12/` — testes WhatsApp (untracked)
- `tests/test_tenant/` — testes tenant (untracked)

### CI/CD
- `.github/workflows/tests.yml` criado na fase 11 ✅
- Falta: workflow de deploy, lint, type check

---

## Convenções

- **Commits:** `tipo(escopo): descrição` — ex: `feat(fase-11): ...`, `fix(docker): ...`
- **Branches:** uma branch por fase — `fase-N`
- **PRs:** abertos para `main` ao concluir cada fase
- **TDD:** testes criados antes/junto com a implementação (obrigatório a partir da fase 8)
- **Alembic:** migrações em `alembic/versions/` para mudanças de schema em produção
- **entrypoint.sh:** seed automático de usuário admin, agentes e servidores MCP ao subir o container
