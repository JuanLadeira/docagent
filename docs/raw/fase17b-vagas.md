# Fase 17b — Pipeline Multi-Agente de Vagas

## Visão Geral

Módulo `vagas` do DocAgent que implementa uma esteira de 4 agentes LangGraph. O usuário faz upload do currículo em PDF, os agentes analisam o perfil, buscam vagas compatíveis em múltiplas fontes, personalizam o currículo/carta para cada vaga e registram as candidaturas. Interface via Vue 3 (nova seção `/vagas` no frontend existente). O apply é semi-automático: o agente abre a URL da vaga e o usuário finaliza manualmente.

Branchamento: `fase-17b` a partir de `fase-17`.

---

## Arquitetura do Pipeline

### Fluxo — 4 nós sequenciais LangGraph

```
upload PDF (endpoint POST /api/vagas/pipeline)
  → asyncio.create_task()
  → START
  → [nó 1] cv_analyzer     — LLM extrai perfil estruturado, salva Candidato
  → [nó 2] job_searcher    — busca vagas (DDG + Gupy + LinkedIn + Indeed), salva Vaga[]
  → [nó 3] personalizer    — gera resumo + carta por vaga, salva Candidatura[]
  → [nó 4] registrar       — finaliza PipelineRun, broadcast SSE CONCLUIDO
  → END
```

O pipeline roda como `asyncio.create_task()` — sem Celery/Redis no MVP. Progresso reportado via SSE (mesmo padrão de `atendimento/sse.py`).

### PipelineVagasState

TypedDict simples — **NÃO usa `add_messages`** (é um pipeline de transformação de dados, não agente conversacional):

```python
class PipelineVagasState(TypedDict):
    tenant_id: int
    usuario_id: int
    pipeline_run_id: int
    cv_text: str
    cv_filename: str
    perfil: dict | None          # produzido pelo nó 1
    candidato_id: int | None     # produzido pelo nó 1
    vagas: list[dict]            # produzido pelo nó 2
    candidaturas: list[dict]     # produzido pelo nó 3
    erro: str | None
```

Cada nó retorna `dict` parcial — LangGraph faz merge semântico no state.

---

## Modelos de Dados

### Enums

```python
class PipelineStatus(str, Enum):
    PENDENTE = "PENDENTE"
    ANALISANDO_CV = "ANALISANDO_CV"
    BUSCANDO_VAGAS = "BUSCANDO_VAGAS"
    PERSONALIZANDO = "PERSONALIZANDO"
    REGISTRANDO = "REGISTRANDO"
    CONCLUIDO = "CONCLUIDO"
    ERRO = "ERRO"

class CandidaturaStatus(str, Enum):
    AGUARDANDO_ENVIO = "AGUARDANDO_ENVIO"
    ENVIADA = "ENVIADA"
    REJEITADA = "REJEITADA"

class FonteVaga(str, Enum):
    DUCKDUCKGO = "DUCKDUCKGO"
    GUPY = "GUPY"
    LINKEDIN = "LINKEDIN"
    INDEED = "INDEED"
```

### Tabelas (herdam `Base` com id/created_at/updated_at)

**Candidato**
| Coluna | Tipo | Notas |
|--------|------|-------|
| tenant_id | FK Tenant | obrigatório |
| usuario_id | FK Usuario | obrigatório |
| nome | String(200) | extraído do CV |
| email | String(200) | extraído do CV |
| telefone | String(50) | extraído do CV |
| skills | JSON | lista de strings |
| experiencias | JSON | lista de {cargo, empresa, periodo, descricao} |
| formacao | JSON | lista de {grau, curso, instituicao, ano} |
| cargo_desejado | String(200) | principal cargo extraído |
| resumo | Text | parágrafo resumo profissional |
| cv_filename | String(500) | nome do arquivo original |

**PipelineRun**
| Coluna | Tipo | Notas |
|--------|------|-------|
| tenant_id | FK Tenant | obrigatório |
| usuario_id | FK Usuario | obrigatório |
| candidato_id | FK Candidato, nullable | preenchido após nó 1 |
| status | String(50), default "PENDENTE" | enum PipelineStatus |
| etapa_atual | String(100) | label legível para UI |
| erro | Text, nullable | mensagem de erro |
| vagas_encontradas | Integer, default 0 | contagem final |
| candidaturas_criadas | Integer, default 0 | contagem final |

**Vaga**
| Coluna | Tipo | Notas |
|--------|------|-------|
| tenant_id | FK Tenant | isolamento multi-tenant |
| pipeline_run_id | FK PipelineRun, CASCADE | cascade delete |
| titulo | String(300) | título da vaga |
| empresa | String(200) | nome da empresa |
| localizacao | String(200) | cidade/estado/remoto |
| descricao | Text | corpo da vaga |
| requisitos | Text | requisitos técnicos |
| url | String(1000) | link original |
| fonte | String(50) | enum FonteVaga |
| match_score | Float, default 0.0 | 0.0–1.0 |
| raw_data | JSON | payload bruto da fonte |

**Candidatura**
| Coluna | Tipo | Notas |
|--------|------|-------|
| tenant_id | FK Tenant | isolamento multi-tenant |
| pipeline_run_id | FK PipelineRun, CASCADE | cascade delete |
| vaga_id | FK Vaga | associação |
| candidato_id | FK Candidato | associação |
| resumo_personalizado | Text | CV adaptado para a vaga |
| carta_apresentacao | Text | carta de apresentação personalizada |
| status | String(50), default "AGUARDANDO_ENVIO" | enum CandidaturaStatus |

### Relacionamentos

```
Tenant → PipelineRun[] (1:N)
Tenant → Candidato[] (1:N)
PipelineRun → Vaga[] (1:N, cascade)
PipelineRun → Candidatura[] (1:N, cascade)
Candidato → PipelineRun[] (1:N)
Vaga → Candidatura (1:1)
```

---

## Estrutura de Arquivos

```
src/docagent/vagas/
├── __init__.py
├── models.py              — 4 models + 3 enums
├── schemas.py             — Pydantic schemas (Public/Create/Update por model)
├── pipeline_state.py      — PipelineVagasState TypedDict
├── pipeline.py            — build_pipeline_graph(db_factory, sse_manager, llm=None)
├── services.py            — CandidatoService, PipelineRunService, VagaService, CandidaturaService
├── router.py              — APIRouter prefix="/api/vagas"
├── sse.py                 — VagasPipelineSseManager
├── nodes/
│   ├── __init__.py
│   ├── cv_analyzer.py     — make_cv_analyzer_node()
│   ├── job_searcher.py    — make_job_searcher_node()
│   ├── personalizer.py    — make_personalizer_node()
│   └── registrar.py       — make_registrar_node()
└── sources/
    ├── __init__.py
    ├── base.py            — JobSource Protocol
    ├── duckduckgo.py      — DuckDuckGoSource
    ├── gupy.py            — GupySource
    ├── linkedin.py        — LinkedInSource
    └── indeed.py          — IndeedSource

tests/test_vagas/
├── conftest.py
├── test_cv_analyzer.py
├── test_job_sources.py
├── test_personalizer.py
├── test_services.py
└── test_router.py

frontend/src/
├── api/vagasClient.ts
└── views/vagas/
    ├── VagasView.vue
    ├── PipelineDetalheView.vue
    └── CandidaturaDetalheView.vue
```

---

## Endpoints FastAPI

```
POST   /api/vagas/pipeline                    — upload PDF → cria run → lança task → 201
GET    /api/vagas/pipeline/{run_id}/eventos   — SSE progresso (text/event-stream)
GET    /api/vagas/pipelines                   — lista runs do tenant (paginado)
GET    /api/vagas/pipelines/{run_id}          — detalhe com vagas + candidaturas
GET    /api/vagas/vagas                       — ?pipeline_run_id=&min_score=
GET    /api/vagas/candidaturas                — ?pipeline_run_id=&status=
GET    /api/vagas/candidaturas/{id}           — detalhe com textos completos
PATCH  /api/vagas/candidaturas/{id}           — {status: ENVIADA | REJEITADA}
```

### POST /api/vagas/pipeline

```python
# multipart/form-data
# field: cv (UploadFile, PDF obrigatório)

# Response 201:
{
  "pipeline_run_id": 42,
  "status": "PENDENTE",
  "message": "Pipeline iniciado. Acompanhe o progresso via /api/vagas/pipeline/42/eventos"
}
```

---

## Detalhes dos Nós

### Nó 1 — cv_analyzer

**Responsabilidade:** Extrair texto do PDF e estruturar o perfil do candidato via LLM.

**Implementação:**
- Recebe `cv_text` (extraído no endpoint com `PyMuPDFLoader`) e `cv_filename`
- Limitar `cv_text[:8000]` antes de enviar ao LLM para evitar context overflow
- `llm.with_structured_output(PerfilExtraido, method="json_mode")` — obrigatório para Ollama
- Fallback: se JSON malformado, retorna `PerfilExtraido` com campos vazios em vez de travar
- Persiste `Candidato` via `CandidatoService`
- Emite SSE: `{"type": "PROGRESSO", "etapa": "ANALISANDO_CV", ...}`

**Schema de output do LLM:**
```python
class PerfilExtraido(BaseModel):
    nome: str = ""
    email: str = ""
    telefone: str = ""
    cargo_desejado: str = ""
    skills: list[str] = []
    experiencias: list[dict] = []
    formacao: list[dict] = []
    resumo: str = ""
```

### Nó 2 — job_searcher

**Responsabilidade:** Buscar vagas compatíveis em múltiplas fontes e calcular match_score.

**Implementação:**
- Executa todas as sources em paralelo via `asyncio.gather(*tasks, return_exceptions=True)`
- Sources com exceção retornam `[]` — fonte com falha não derruba pipeline
- `_calcular_match_score(skills_candidato, descricao_vaga)`: conta skills que aparecem na descrição — sem LLM, sem latência
- Top 20 vagas por match_score passam para o nó 3
- Persiste `Vaga[]` via `VagaService`
- Emite SSE: `{"type": "PROGRESSO", "etapa": "BUSCANDO_VAGAS", ...}`

**JobSource Protocol:**
```python
class JobSource(Protocol):
    async def buscar(self, perfil: dict) -> list[dict]: ...
```

### Nó 3 — personalizer

**Responsabilidade:** Gerar resumo e carta de apresentação personalizados por vaga.

**Implementação:**
- Processa vagas **em sequência** (não paralelo) para evitar rate limiting do LLM
- Top 10 vagas do nó 2 (não 20 — o LLM é chamado por vaga)
- Cada chamada LLM: perfil resumido + descrição da vaga → retorna `{resumo, carta}`
- Persiste cada `Candidatura` individualmente ao gerar (não em batch no final)
- Progresso incremental via SSE: `{"type": "PROGRESSO", "etapa": "PERSONALIZANDO", "mensagem": "Personalizando 3/10..."}`

### Nó 4 — registrar

**Responsabilidade:** Finalizar o pipeline e emitir evento de conclusão.

**Implementação:**
- Atualiza `PipelineRun.status = CONCLUIDO`
- Preenche `vagas_encontradas` e `candidaturas_criadas`
- Emite SSE: `{"type": "CONCLUIDO", "vagas_encontradas": 15, "candidaturas_criadas": 10}`
- Em caso de erro em qualquer nó anterior: `{"type": "ERRO", "mensagem": "..."}`

---

## Job Sources

### Gupy API (mais confiável — implementar primeiro)

```python
# GET https://portal.api.gupy.io/api/v1/jobs?jobName=<cargo>&limit=20
# Sem autenticação
# asyncio.sleep(0.5) entre queries consecutivas

async def buscar(self, perfil: dict) -> list[dict]:
    cargo = perfil.get("cargo_desejado", "")
    url = f"https://portal.api.gupy.io/api/v1/jobs?jobName={quote(cargo)}&limit=20"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json().get("data", [])
```

### DuckDuckGo

Reutiliza `DuckDuckGoSearchResults` de `src/docagent/agent/skills/web_search.py`. Busca `"{cargo} site:gupy.io OR site:linkedin.com/jobs"`.

### LinkedIn

httpx sem JavaScript — vai falhar com frequência (Cloudflare, CAPTCHA). Tratar como fonte bônus:

```python
async def buscar(self, perfil: dict) -> list[dict]:
    try:
        # GET https://www.linkedin.com/jobs/search/?keywords=<cargo>&location=Brasil
        # bs4: encontrar <li class="jobs-search__results-list">
        ...
    except Exception:
        return []
```

### Indeed

RSS como fallback antes do HTML scraping:

```python
# br.indeed.com/rss?q=<cargo>&l=Brasil
# Fallback: HTML scraping com bs4
```

---

## SSE — VagasPipelineSseManager

Clone de `atendimento/sse.py` com chave `pipeline_run_id`.

**Eventos:**
```json
{"type": "PROGRESSO", "etapa": "BUSCANDO_VAGAS", "mensagem": "Buscando vagas..."}
{"type": "PROGRESSO", "etapa": "PERSONALIZANDO", "mensagem": "Personalizando 3/10..."}
{"type": "CONCLUIDO", "vagas_encontradas": 15, "candidaturas_criadas": 10}
{"type": "ERRO", "mensagem": "Erro ao analisar CV: ..."}
{"type": "ping"}
```

**Diferença do atendimento:** stream fecha automaticamente quando recebe `CONCLUIDO` ou `ERRO`. O cliente Vue deve fechar o `EventSource` nesses eventos.

---

## Background Task

```python
# router.py
@router.post("/pipeline", status_code=201)
async def iniciar_pipeline(cv: UploadFile, current_user: CurrentUser, ...):
    # 1. Extrair texto do PDF no request (PyMuPDFLoader)
    # 2. Criar PipelineRun com status PENDENTE
    # 3. Criar task que cria suas próprias sessões
    asyncio.create_task(
        _executar_pipeline_com_tratamento_erro(
            tenant_id=current_user.tenant_id,
            usuario_id=current_user.id,
            pipeline_run_id=run.id,
            cv_text=cv_text,
            cv_filename=cv.filename,
        )
    )
    return {"pipeline_run_id": run.id, "status": "PENDENTE", ...}
```

**Sessões de banco:** cada nó cria `async with AsyncSessionLocal() as session: async with session.begin(): ...`. A sessão do request fecha antes da task terminar. Mesma pattern de `whatsapp/router.py`.

---

## Alembic Migration

Arquivo: `alembic/versions/XXXXXX_add_vagas_pipeline.py`

- Usar `String(50)` para enums (não tipo Enum nativo) — compatibilidade SQLite + PostgreSQL
- Tabelas: `candidatos`, `pipeline_runs`, `vagas`, `candidaturas`
- Criar na ordem: candidatos → pipeline_runs → vagas → candidaturas (FKs)
- Padrão `batch_alter_table` para SQLite

---

## Frontend

### vagasClient.ts

```typescript
// POST /api/vagas/pipeline — multipart/form-data com arquivo PDF
export async function iniciarPipeline(cvFile: File): Promise<PipelineRunResponse>

// GET /api/vagas/pipelines — lista com paginação
export async function listarPipelines(): Promise<PipelineRunPublic[]>

// GET /api/vagas/pipelines/{id} — detalhe
export async function getPipeline(id: number): Promise<PipelineRunDetalhe>

// SSE
export function subscribePipelineEventos(
  runId: number,
  onEvent: (e: PipelineEvent) => void,
  onClose: () => void
): EventSource

// PATCH /api/vagas/candidaturas/{id}
export async function atualizarCandidatura(id: number, status: CandidaturaStatus): Promise<void>
```

### VagasView.vue

- Área de drag-and-drop para upload do PDF
- Histórico de PipelineRuns com status visual (badge colorido)
- Link para detalhe de cada run
- Mensagem de onboarding se ainda não há runs

### PipelineDetalheView.vue

- Barra de progresso com etapas (ANALISANDO_CV → BUSCANDO_VAGAS → PERSONALIZANDO → CONCLUIDO)
- Conecta ao SSE e atualiza em tempo real
- Lista de vagas encontradas com match_score (barra colorida)
- Lista de candidaturas geradas
- Fecha EventSource ao receber CONCLUIDO/ERRO

### CandidaturaDetalheView.vue

- Exibe carta de apresentação e resumo personalizado
- Botão "Abrir e aplicar": `window.open(vaga.url, '_blank')` + PATCH status → ENVIADA
- Botão "Rejeitar": PATCH status → REJEITADA
- Status visual da candidatura

### Rotas (router/index.ts)

```typescript
{ path: '/vagas', component: VagasView }
{ path: '/vagas/pipeline/:id', component: PipelineDetalheView }
{ path: '/vagas/candidaturas/:id', component: CandidaturaDetalheView }
```

Menu lateral: adicionar link "Vagas" com ícone de briefcase.

---

## Dependências a Adicionar

```toml
# pyproject.toml
"beautifulsoup4>=4.12.0",
"lxml>=5.0.0",
```

`httpx`, `PyMuPDF` e `langchain-community` já instalados.

---

## Reutilizações do Código Existente

| O quê | De onde |
|-------|---------|
| `PyMuPDFLoader` | `src/docagent/rag/ingest.py` |
| `DuckDuckGoSearchResults` | `src/docagent/agent/skills/web_search.py` |
| `get_llm()` / `get_tenant_llm()` | `src/docagent/agent/llm_factory.py` |
| SSE pattern (queues, subscribe, broadcast) | `src/docagent/atendimento/sse.py` |
| `AsyncSessionLocal` para background tasks | `src/docagent/whatsapp/router.py` |
| `make_*_node` factory pattern | `src/docagent/agent/base.py` |
| `batch_alter_table` Alembic pattern | `alembic/versions/g7h8i9j0k1l2_*` |

---

## Testes (TDD)

### conftest.py

```python
@pytest.fixture
async def mock_llm():
    # LLM que retorna JSON válido para cv_analyzer e personalizer
    ...

@pytest.fixture
def mock_sources():
    # Sources que retornam listas fixas de vagas
    ...
```

### test_cv_analyzer.py
- Testa extração de perfil com CV real (texto curto)
- Testa fallback com JSON malformado
- Testa CV vazio → erro amigável

### test_job_sources.py
- Testa cada source com `httpx.MockTransport`
- Testa source com erro de rede → retorna `[]`
- Testa `_calcular_match_score` com skills conhecidos

### test_personalizer.py
- Testa geração de carta com mock LLM
- Testa processamento sequencial (10 vagas → 10 chamadas LLM)
- Testa persistência individual de candidaturas

### test_services.py
- CandidatoService CRUD
- PipelineRunService atualização de status
- VagaService filtro por pipeline_run_id e min_score
- CandidaturaService atualização de status

### test_router.py
- POST /api/vagas/pipeline com PDF real pequeno
- GET /api/vagas/pipelines — lista isolada por tenant
- GET /api/vagas/pipelines/{id} — isolamento tenant
- PATCH /api/vagas/candidaturas/{id} — atualização de status

---

## Ordem de Implementação

### Sprint 1 — Fundação
1. `vagas/models.py` + enums
2. `vagas/schemas.py`
3. `vagas/pipeline_state.py` + `vagas/sse.py`
4. RED: `tests/test_vagas/test_services.py`
5. GREEN: `vagas/services.py` (4 service classes)
6. Alembic migration: `add_vagas_pipeline`

### Sprint 2 — Nó 1 (CV Analyzer)
7. RED: `tests/test_vagas/test_cv_analyzer.py`
8. GREEN: `nodes/cv_analyzer.py`
9. Validar structured output com Ollama local

### Sprint 3 — Job Sources
10. RED: `tests/test_vagas/test_job_sources.py`
11. GREEN: `sources/gupy.py` (mais confiável, implementar primeiro)
12. GREEN: `sources/duckduckgo.py`
13. GREEN: `sources/linkedin.py` + `sources/indeed.py` (com mocks)
14. GREEN: `nodes/job_searcher.py` (com `_calcular_match_score`)

### Sprint 4 — Nós 3 e 4
15. RED: `tests/test_vagas/test_personalizer.py`
16. GREEN: `nodes/personalizer.py` + `nodes/registrar.py`

### Sprint 5 — Pipeline + Endpoints
17. `vagas/pipeline.py`: `build_pipeline_graph()`
18. RED: `tests/test_vagas/test_router.py`
19. GREEN: `vagas/router.py`
20. `api.py`: `include_router(vagas_router)`

### Sprint 6 — Frontend
21. `frontend/src/api/vagasClient.ts`
22. `VagasView.vue` (upload + histórico)
23. `PipelineDetalheView.vue` (SSE progresso + resultados)
24. `CandidaturaDetalheView.vue` (carta + aplicar)
25. `router/index.ts`: rotas `/vagas`, `/vagas/pipeline/:id`, `/vagas/candidaturas/:id`
26. Menu lateral: link "Vagas"

### Sprint 7 — Integração
27. Teste E2E com PDF real
28. Ajuste de prompts com outputs reais do LLM
29. Verificar isolamento multi-tenant

---

## Gotchas

- **`ainvoke()` no LangGraph é async nativo** — não envolver em `run_in_executor`. Só usar executor para chamadas síncronas *dentro* dos nós (ex: `PyMuPDFLoader` que é síncrono)
- **`method="json_mode"`** no structured_output — obrigatório para Ollama local (não suporta tool calling confiável)
- **PDF sem texto (scaneado)** — verificar `cv_text.strip()` vazio → 422 com mensagem amigável no endpoint
- **SSE fecha ao receber CONCLUIDO/ERRO** — diferente do atendimento (que é perpétuo); cliente Vue deve fechar `EventSource` nesses eventos
- **Background task vs sessão do request** — task cria sessões próprias via `AsyncSessionLocal()`; a sessão do request fecha antes da task terminar
- **Scraping LinkedIn/Indeed vai falhar em produção** — tratar como fonte bônus, não crítica; `try/except Exception: return []`
- **`asyncio.create_task` com multi-workers** — task vive no worker que a criou; `PipelineRun` fica `PENDENTE` se worker morrer (aceitável para MVP)
- **Alembic + SQLite + Enum** — usar `String(50)` na migration, não tipo Enum nativo do SQLAlchemy
- **Top 20 → Top 10** — nó 2 passa top 20 por score ao nó 3, mas nó 3 processa apenas top 10 (LLM é chamado por vaga)
- **`PyMuPDFLoader` é síncrono** — envolver em `asyncio.to_thread()` quando chamado dentro de nó async
