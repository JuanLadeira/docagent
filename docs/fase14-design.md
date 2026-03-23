# Fase 14 — Design: Atendimentos em Tempo Real, Módulo Contatos e Otimizações de Latência

## Visão Geral

Esta fase entregou três conjuntos de melhorias independentes:

1. **Atendimentos em tempo real** — substituiu polling por SSE com reconexão automática
2. **Módulo Contatos** — cadastro de contatos vinculado ao histórico de atendimentos
3. **Otimizações de latência** — eliminou overhead desnecessário no pipeline de resposta do agente

---

## Parte 1 — Atendimentos em Tempo Real (SSE)

### Problema

A tela de atendimentos usava `setInterval` para consultar a API a cada poucos segundos. Isso gerava:

- Atraso de até N segundos entre um evento (nova mensagem, mudança de status) e a atualização visual
- Requisições constantes mesmo sem nenhuma mudança (desperdício)
- Falsa impressão de "dados sumidos" quando a API reiniciava e o polling retornava lista vazia momentaneamente

### Solução

**SSE (Server-Sent Events) tenant-level** — um stream persistente por operador logado, que recebe eventos push do servidor assim que acontecem.

```
Operador abre a tela
     │
     └─ GET /api/atendimentos/eventos (SSE, mantém conexão aberta)
          │
          ├─ NOVO_ATENDIMENTO      → insere no topo da lista
          ├─ ATENDIMENTO_ATUALIZADO → atualiza status/prioridade na lista
          └─ ping (30s)            → keepalive para proxies
```

**Reconexão automática com backoff exponencial** — se a API reiniciar ou a conexão cair, o frontend tenta reconectar automaticamente: 2s → 4s → 8s → 16s → 30s. Ao reconectar, recarrega a lista completa para recuperar eventos perdidos durante a queda.

**Banner de status** — enquanto o SSE não está conectado, a lista exibe:
- Amarelo "Conectando..." na primeira conexão
- Vermelho "Reconectando..." após queda

### Arquitetura SSE

**Backend (`src/docagent/atendimento/sse.py`)**

Dois gerenciadores de filas:
- `AtendimentoSseManager` — por `atendimento_id` (mensagens em tempo real na conversa)
- `AtendimentoListaSseManager` — por `tenant_id` (eventos de lista para todos os operadores do tenant)

**Frontend (`frontend/src/api/client.ts`)**

`subscribeAtendimentoLista(onEvent, onStatus)`:
- Usa `fetch + ReadableStream` (EventSource nativo não suporta header `Authorization`)
- Loop de reconexão interno com backoff
- Callback `onStatus('connecting' | 'connected' | 'disconnected')` para o componente reagir

### Trade-offs

| | |
|---|---|
| **Benefício** | Atualizações instantâneas, zero polling, UX fluida mesmo em alta volumetria |
| **Custo** | Uma conexão HTTP persistente por operador logado |
| **Reconexão** | Backoff até 30s — aceitável; evento perdido durante queda é recuperado com refetch |
| **uvicorn reload** | SSE connections longas impediam reload gracioso → `--timeout-graceful-shutdown 3` resolve |

### Arquivos Modificados

| Arquivo | Mudança |
|---|---|
| `src/docagent/atendimento/sse.py` | `AtendimentoListaSseManager` (broadcast por tenant) |
| `src/docagent/atendimento/router.py` | `GET /api/atendimentos/eventos` + broadcasts em assumir/devolver/encerrar |
| `src/docagent/whatsapp/router.py` | Emite SSE ao criar atendimento via webhook |
| `frontend/src/api/client.ts` | `subscribeAtendimentoLista` com reconexão e `onStatus` |
| `frontend/src/views/atendimento/AtendimentoView.vue` | Remove polling, adiciona banner de status SSE, abas Ativos/Histórico |
| `docker-compose.yml` | `--timeout-graceful-shutdown 3` no comando uvicorn |

---

## Parte 2 — Módulo Contatos

### Problema

Os atendimentos exibiam apenas o número de telefone do contato — sem nome, sem histórico unificado, sem forma de saber quem era a pessoa do outro lado. Operadores precisavam decorar números.

### Solução

Modelo `Contato` com vínculo explícito a atendimentos, auto-linking retroativo e telas dedicadas.

### Modelo de Dados

```
Contato
├─ id
├─ numero          (e.g. "5511999999999")
├─ instancia_id    (FK → WhatsappInstancia)
├─ tenant_id       (FK → Tenant)
├─ nome
├─ email           (opcional)
├─ notas           (opcional)
└─ UniqueConstraint(numero, instancia_id, tenant_id)

Atendimento
├─ ...
├─ contato_id      (FK → Contato, nullable)
├─ nome_contato    (desnormalizado para exibição rápida)
└─ prioridade      (NORMAL | ALTA | URGENTE)
```

`nome_contato` é desnormalizado intencionalmente: permite exibir o nome na lista sem JOIN, e reflete o nome no momento do atendimento mesmo se o contato for renomeado depois.

### Fluxo: Criar Contato

```
Operador clica "+ Adicionar contato" no atendimento
     │
     └─ POST /api/atendimentos/contatos { numero, nome, email, notas, instancia_id }
          │
          ├─ Cria Contato
          ├─ Busca todos atendimentos do mesmo número+instância sem contato_id
          ├─ Seta contato_id e nome_contato em cada um (backfill retroativo)
          └─ Emite SSE ATENDIMENTO_ATUALIZADO para cada atendimento atualizado
```

### Fluxo: Webhook recebe mensagem de número já cadastrado

```
Mensagem chega → webhook busca Contato pelo número+instância
     │
     ├─ Encontrou → Atendimento criado com contato_id + nome_contato preenchidos
     └─ Não encontrou → Atendimento criado com contato_id=None, nome_contato=None
```

### UX

- **Lista de atendimentos**: nome do contato como texto principal (bold), número como texto secundário cinza abaixo
- **Cabeçalho do atendimento**: nome em destaque + chip "Ver contato →" indigo ao lado; número como texto secundário
- **ContatoView**: lista de contatos com busca por nome ou número
- **ContatoDetalheView**: ficha do contato (nome, email, notas editáveis) + histórico completo de atendimentos

### Migration Alembic

`alembic/versions/b2c3d4e5f6a7_add_contato.py`

Nota técnica: SQLite não suporta `ADD COLUMN ... REFERENCES` via `ALTER TABLE`. A foreign key `contato_id → contato.id` é declarada apenas no ORM (SQLAlchemy), não na migration DDL.

### Arquivos Modificados

| Arquivo | Mudança |
|---|---|
| `src/docagent/atendimento/models.py` | `Contato`, `Prioridade`, relação `contato` em `Atendimento` |
| `src/docagent/atendimento/schemas.py` | `ContatoCreate/Update/Public/Detalhe`, campos `contato_id`/`prioridade` |
| `src/docagent/atendimento/router.py` | CRUD `/contatos`, rota `/contatos/{id}` antes de `/{atendimento_id}` |
| `alembic/versions/b2c3d4e5f6a7_add_contato.py` | Migration: tabela `contato` + colunas |
| `frontend/src/api/client.ts` | Tipos `Contato*` + métodos `criarContato`, `listContatos`, `getContato`, `atualizarContato` |
| `frontend/src/views/atendimento/ContatoView.vue` | Lista de contatos com busca |
| `frontend/src/views/atendimento/ContatoDetalheView.vue` | Ficha + histórico |
| `frontend/src/router/index.ts` | Rotas `/contatos` e `/contatos/:id` |
| `frontend/src/App.vue` | Item "Contatos" na nav (visível para owner) |

---

## Parte 3 — Otimizações de Latência do Agente WhatsApp

### Problema

Quando uma mensagem WhatsApp chega ao sistema, o agente demora para responder. O delay acumulado tem três causas distintas:

```
Mensagem chega via webhook
     │
     ├─ 1. DB queries (instância, agente, atendimento)  ~50ms   OK
     │
     ├─ 2. ConfigurableAgent(...).build()               ~50ms   ← desnecessário toda mensagem
     │       └─ instancia ChatOllama
     │       └─ llm.bind_tools(tools)
     │       └─ StateGraph.compile()
     │
     ├─ 3. agent.run() — síncrono, bloqueia event loop  ~3-8s   ← bloqueia todo o servidor
     │       └─ se modelo não está carregado na VRAM:   +10-15s ← cold start do Ollama
     │
     └─ resposta enviada ao usuário
```

**Impacto percebido:** primeira mensagem do dia demora 15-25s. Mensagens subsequentes demoram 3-8s.

---

## Fix 1 — Keep Model Warm (startup warmup)

### Causa raiz

O Ollama descarrega o modelo da VRAM após inatividade (padrão: 5 minutos). A primeira mensagem após esse período exige recarregar ~5GB do `qwen2.5:7b` antes de inferir — esse é o "delay inicial" mais perceptível.

### Solução

Adicionar um `lifespan` context manager no FastAPI (`api.py`) que envia uma inferência mínima ao LLM durante o startup do servidor. O modelo é carregado na VRAM antes de qualquer mensagem chegar.

```
Container sobe
    │
    └─ lifespan startup → llm.invoke(["olá"]) via run_in_executor
                           Ollama carrega modelo na VRAM (~10s, uma vez por boot)
                           "[startup] Modelo aquecido."

Primeira mensagem → modelo já está na VRAM → sem cold start
```

### Trade-offs

| | |
|---|---|
| **Benefício** | Elimina o cold start. Primeira mensagem responde tão rápido quanto as seguintes. |
| **Custo** | O container demora ~10s a mais para ficar pronto após boot. |
| **Limitação** | Se o Ollama descarregar o modelo por inatividade longa *depois* do boot, o cold start volta. O fix permanente seria `OLLAMA_KEEP_ALIVE=-1` no host. |
| **Resiliência** | Falha silenciosa — se o Ollama estiver offline no startup, o servidor sobe normalmente sem warmup. |

### Código

**`src/docagent/api.py`**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        llm = ChatOllama(model=os.getenv("LLM_MODEL", "qwen2.5:7b"), ...)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, llm.invoke, [HumanMessage(content="olá")])
        print("[startup] Modelo aquecido.")
    except Exception as e:
        print(f"[startup] Warmup falhou (Ollama offline?): {e}")
    yield

app = FastAPI(..., lifespan=lifespan)
```

---

## Fix 2 — Agent no Thread Pool

### Causa raiz

`agent.run()` usa `ChatOllama.invoke()` que internamente faz HTTP com `requests` (biblioteca **síncrona**). Quando chamado dentro de `async def _processar_mensagem_recebida()`, bloqueia o event loop do asyncio durante toda a inferência.

Impacto: enquanto o Ollama processa uma mensagem, nenhuma outra request é atendida — nem SSE do frontend, nem webhooks de outras instâncias.

```
Sem executor (atual):
Event loop: [webhook A] [====== LLM A 5s ======] [webhook B] [====== LLM B 5s ======]

Com executor:
Event loop: [webhook A] [webhook B] [SSE] [SSE] [resp A] [resp B]
Thread 1:              [====== LLM A 5s ======]
Thread 2:                          [====== LLM B 5s ======]
```

### Solução

`asyncio.get_event_loop().run_in_executor(None, fn, *args)` envia a função síncrona para o `ThreadPoolExecutor` padrão do Python e aguarda o resultado de forma assíncrona, sem bloquear o event loop.

### Trade-offs

| | |
|---|---|
| **Benefício** | Event loop livre durante inferência. Múltiplas instâncias processadas em paralelo. Frontend e SSE continuam responsivos. |
| **Custo** | Não reduz a latência individual — o LLM ainda demora o mesmo para aquele usuário. |
| **Limite** | ThreadPoolExecutor padrão: `min(32, cpu_count + 4)` threads. Irrelevante para a escala atual. |

### Código

**`src/docagent/whatsapp/router.py`**

```python
# Antes (síncrono, bloqueia event loop)
final_state = agent.run(conteudo, state)

# Depois (assíncrono, libera event loop)
loop = asyncio.get_event_loop()
final_state = await loop.run_in_executor(None, agent.run, conteudo, state)
```

---

## Fix 3 — Cache do Agente Construído

### Causa raiz

A cada mensagem, o código executa:

```python
agent = ConfigurableAgent(config, ...).build()
```

`build()` → `_build_graph()`: instancia `ChatOllama`, chama `llm.bind_tools(tools)`, compila o `StateGraph` do LangGraph. São ~50ms de overhead por mensagem — desnecessário quando o mesmo agente atende múltiplas conversas.

### Solução

Cache em memória no módulo `whatsapp/router.py`, keyed por `(agente_id, skill_names, system_prompt)`. A chave muda automaticamente se o operador reconfigura o agente no painel, forçando um rebuild.

O agente cacheado é **stateless** — o estado da conversa é gerenciado pelo `SessionManager` existente (`dependencies.py`). Múltiplas conversas usam a mesma instância sem conflito.

### Trade-offs

| | |
|---|---|
| **Benefício** | Elimina ~50ms de overhead por mensagem após o primeiro build. LangGraph compilado uma vez. |
| **Cache invalidation** | Automática — a chave inclui skill_names e system_prompt. Config muda → miss → rebuild. |
| **Thread safety** | `dict.__setitem__` em CPython é GIL-protected. Sem race condition na prática. |
| **Memória** | Cada agente cacheado usa KBs. Negligível com poucos agentes distintos. |
| **Persistência** | Cache em memória: perdido ao reiniciar o container. Sem impacto funcional — reconstruído na próxima mensagem. |

### Código

**`src/docagent/whatsapp/router.py`**

```python
_agent_cache: dict[tuple, BaseAgent] = {}

def _get_or_build_agent(agente_obj: Agente) -> BaseAgent:
    cache_key = (
        agente_obj.id,
        tuple(agente_obj.skill_names),
        agente_obj.system_prompt or "",
    )
    if cache_key not in _agent_cache:
        config = AgentConfig(id=str(agente_obj.id), ...)
        _agent_cache[cache_key] = ConfigurableAgent(config, ...).build()
    return _agent_cache[cache_key]

# No webhook:
agent = _get_or_build_agent(agente_obj)  # substitui as 6 linhas de build inline
```

---

### Arquivos Modificados (Parte 3)

| Arquivo | Mudança |
|---|---|
| `src/docagent/api.py` | `lifespan` context manager com warmup do LLM no startup |
| `src/docagent/whatsapp/router.py` | `_agent_cache` + `_get_or_build_agent()` + `run_in_executor` |

### Impacto Combinado

```
Antes:  primeira msg = 15-25s  │  msgs seguintes = 3-8s  │  event loop bloqueado
Depois: primeira msg = 3-8s    │  msgs seguintes = 3-8s  │  event loop livre
        (modelo já aquecido)      (agente cacheado)         (thread pool)
```

O tempo de inferência do LLM em si não muda — isso dependeria de modelo mais rápido ou GPU mais potente. O que muda é eliminar o overhead desnecessário ao redor da inferência.

---

## Verificação

### SSE e Contatos

```bash
# 1. Abrir a tela de atendimentos e reiniciar a API
docker compose restart api
# Esperado: banner "Reconectando..." aparece na lista, some após reconexão
# Esperado: lista recarregada automaticamente, dados não "somem"

# 2. Criar um contato via "+ Adicionar contato"
# Esperado: nome aparece imediatamente no cabeçalho e na lista (via SSE ATENDIMENTO_ATUALIZADO)

# 3. Enviar mensagem de um número já cadastrado como contato
# Esperado: atendimento criado com nome_contato preenchido desde o início
```

### Latência do Agente

```bash
# 1. Reiniciar o container e observar o warmup nos logs
docker compose up -d --no-deps api
docker compose logs api -f
# Esperado: "[startup] Modelo aquecido." antes do "Uvicorn running"

# 2. Enviar mensagem WhatsApp imediatamente após o boot
# Esperado: resposta em ~3-8s (sem cold start)

# 3. Enviar mensagens de duas instâncias simultaneamente
# Esperado: logs de ambas intercalados (processamento paralelo)

# 4. Reconfigurar o agente no painel e enviar nova mensagem
# Esperado: nova instância construída (cache miss por nova chave)
```
