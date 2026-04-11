# Wiki — DocAgent / z3ndocs

> Catálogo de todo o conhecimento compilado. Atualizado pelo LLM a cada sprint.
> Para specs de planejamento, ver [`docs/raw/`](../raw/).

---

## Estado e Roadmap

- [estado.md](estado.md) — estado atual do sistema, o que está em andamento, próximos passos
- [gotchas.md](gotchas.md) — armadilhas acumuladas, erros recorrentes, coisas a não esquecer
- [log.md](log.md) — histórico cronológico de sprints, fases e decisões

---

## Fases Implementadas

| Página | Tema | Status |
|--------|------|--------|
| [fases/1-7.md](fases/1-7.md) | RAG, LangGraph, Memória, API, BaseAgent, Skills, Streamlit | ✅ |
| [fases/8.md](fases/8.md) | Auth JWT + Multi-tenant + Alembic | ✅ |
| [fases/10.md](fases/10.md) | Frontend Vue 3 + Pinia + CRUD agentes | ✅ |
| [fases/11.md](fases/11.md) | MCP: skills dinâmicas via Model Context Protocol | ✅ |
| [fases/12.md](fases/12.md) | WhatsApp via Evolution API v2.3.7 | ✅ |
| [fases/13.md](fases/13.md) | Atendimento WhatsApp (máquina de estados, SSE) | ✅ |
| [fases/14.md](fases/14.md) | Tempo real + Contatos (SSE, reconexão) | ✅ |
| [fases/15.md](fases/15.md) | Documentos por agente (upload, RAG isolado) | ✅ |
| [fases/16.md](fases/16.md) | Telegram Bot (webhook, polling, atendimento) | ✅ |
| [fases/17.md](fases/17.md) | Planos, Assinaturas, Quotas + Admin billing UI | ✅ |
| [fases/17b.md](fases/17b.md) | Pipeline de Vagas (candidatos, CV, ranking) | ✅ |
| [fases/18.md](fases/18.md) | Áudio STT + TTS (WhatsApp + Telegram) | 🟡 em andamento |

---

## Módulos do Sistema

| Página | Módulo | Descrição curta |
|--------|--------|-----------------|
| [modulos/agente.md](modulos/agente.md) | `agente/` | CRUD de agentes, skill_names, system_prompt |
| [modulos/audio.md](modulos/audio.md) | `audio/` | STT/TTS, AudioConfig, cascade de config |
| [modulos/auth.md](modulos/auth.md) | `auth/` | JWT dual (user + admin), current_user |
| [modulos/atendimento.md](modulos/atendimento.md) | `atendimento/` | Máquina de estados, SSE, Contatos |
| [modulos/langgraph.md](modulos/langgraph.md) | `agents/`, `base_agent.py` | LangGraph StateGraph, ReAct, memória |
| [modulos/mcp.md](modulos/mcp.md) | `mcp_server/` | Servidores MCP stdio, descoberta de tools |
| [modulos/plano.md](modulos/plano.md) | `plano/`, `assinatura/` | Planos, quotas, assinaturas por tenant |
| [modulos/telegram.md](modulos/telegram.md) | `telegram/` | Bot Telegram, webhook, áudio |
| [modulos/whatsapp.md](modulos/whatsapp.md) | `whatsapp/` | Evolution API v2, webhook, áudio |

---

## Decisões Arquiteturais

| Página | Decisão |
|--------|---------|
| [decisoes/fk-agente-tablename.md](decisoes/fk-agente-tablename.md) | Tablename é "agente" não "agentes" |
| [decisoes/system-defaults-simplenamespace.md](decisoes/system-defaults-simplenamespace.md) | System defaults como SimpleNamespace, não ORM |
| [decisoes/asyncexitstack-mcp.md](decisoes/asyncexitstack-mcp.md) | AsyncExitStack para ciclo de vida dos subprocessos MCP |
| [decisoes/jwt-dual.md](decisoes/jwt-dual.md) | JWT dual: user vs admin com prefixo `admin:` |
| [decisoes/audio-cascade.md](decisoes/audio-cascade.md) | Cascata de config: agente → tenant → system defaults |
| [decisoes/tdd-texto-path.md](decisoes/tdd-texto-path.md) | Path de texto mantido inline no webhook (não refatorado) |
