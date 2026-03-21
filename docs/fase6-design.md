# Fase 6 — Skills, Multi-Agent e Upload de Documentos

## Objetivo

Evoluir o DocAgent de um agente fixo para um sistema extensível onde:

1. **Skills** são módulos independentes e reutilizáveis
2. **Agentes** são configurados por combinações de skills
3. **Upload de documentos** é feito pelo próprio chat (RAG por sessão)
4. **UI** mostra loading durante geração, seleção de agente e upload inline

Os 150 testes existentes são preservados. Novos testes cobrem cada camada.

---

## Estrutura de arquivos

```
src/docagent/
├── skills/
│   ├── __init__.py
│   ├── base_skill.py          ← protocolo Skill (nome, descrição, ícone, tool)
│   ├── rag_search.py          ← skill de busca em documentos (ChromaDB)
│   └── web_search.py          ← skill de busca na web (DuckDuckGo)
│
├── agents/
│   ├── __init__.py
│   ├── registry.py            ← AGENT_REGISTRY + AgentConfig
│   └── configurable_agent.py  ← ConfigurableAgent(BaseAgent)
│
├── schemas/
│   └── chat.py                ← adiciona AgentInfo, SkillInfo, UploadResponse
│
├── services/
│   ├── chat_service.py        ← sem mudanças
│   └── ingest_service.py      ← IngestService: recebe bytes, retorna collection_id
│
├── routers/
│   ├── chat.py                ← adiciona agent_id ao ChatRequest
│   ├── agents.py              ← GET /agents
│   └── documents.py           ← POST /documents/upload
│
└── dependencies.py            ← get_agent agora recebe agent_id
```

---

## Skills — `skills/base_skill.py`

Protocolo que toda skill deve cumprir. Usa `Protocol` (duck typing) em vez de
ABC para não forçar herança — qualquer objeto com esses atributos é uma skill.

```python
from typing import Protocol
from langchain_core.tools import BaseTool

class Skill(Protocol):
    name: str           # identificador único: "rag_search"
    label: str          # label UI: "Busca em Documentos"
    icon: str           # emoji: "🔍"
    description: str    # descrição para o LLM

    def as_tool(self) -> BaseTool: ...
```

---

## Skills concretas

### `skills/rag_search.py`

```python
class RagSearchSkill:
    name = "rag_search"
    label = "Busca em Documentos"
    icon = "🔍"
    description = "Busca semântica nos documentos PDF carregados"

    def __init__(self, collection: str = "docagent"):
        self._collection = collection   # permite RAG por sessão

    def as_tool(self) -> BaseTool:
        # extrai a @tool atual de tools.py, parametrizada pela collection
        ...
```

### `skills/web_search.py`

```python
class WebSearchSkill:
    name = "web_search"
    label = "Busca na Web"
    icon = "🌐"
    description = "Busca informações atuais na internet"

    def as_tool(self) -> BaseTool:
        return DuckDuckGoSearchRun(name="web_search")
```

---

## Agentes — `agents/registry.py`

```python
from dataclasses import dataclass, field

@dataclass
class AgentConfig:
    id: str
    name: str
    description: str
    skill_names: list[str]   # referências às skills pelo nome

AGENT_REGISTRY: dict[str, AgentConfig] = {
    "doc-analyst": AgentConfig(
        id="doc-analyst",
        name="Analista de Documentos",
        description="Especializado em analisar PDFs carregados pelo usuário.",
        skill_names=["rag_search", "web_search"],
    ),
    "web-researcher": AgentConfig(
        id="web-researcher",
        name="Pesquisador Web",
        description="Busca informações atuais na internet.",
        skill_names=["web_search"],
    ),
}
```

---

## ConfigurableAgent — `agents/configurable_agent.py`

Substitui `DocAgent`. Recebe um `AgentConfig` e instancia as skills corretas.

```python
class ConfigurableAgent(BaseAgent):
    def __init__(self, config: AgentConfig, session_collection: str | None = None):
        super().__init__()
        self._config = config
        self._session_collection = session_collection   # RAG por sessão

    @property
    def tools(self) -> list:
        skill_map = build_skill_map(self._session_collection)
        return [
            skill_map[name].as_tool()
            for name in self._config.skill_names
            if name in skill_map
        ]

    @property
    def system_prompt(self) -> str:
        tool_lines = "\n".join(
            f"- {s.name}: {s.description}"
            for s in self._active_skills()
        )
        return BASE_SYSTEM_PROMPT.format(tools=tool_lines)
```

---

## Schemas — adições em `schemas/chat.py`

```python
class SkillInfo(BaseModel):
    name: str
    label: str
    icon: str
    description: str

class AgentInfo(BaseModel):
    id: str
    name: str
    description: str
    skills: list[SkillInfo]

class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"
    agent_id: str = "doc-analyst"   # novo campo

class UploadResponse(BaseModel):
    filename: str
    chunks: int
    collection_id: str
```

---

## IngestService — `services/ingest_service.py`

Encapsula o pipeline de ingestão. Recebe bytes (do upload HTTP) e devolve
o `collection_id` criado — que é passado ao `ConfigurableAgent` para o RAG
buscar apenas nos documentos da sessão.

```python
class IngestService:
    def ingest(self, filename: str, content: bytes, session_id: str) -> dict:
        """
        1. Salva o arquivo em /tmp/{session_id}/{filename}
        2. Chama load_pdfs() + split_documents()
        3. Chama build_vectorstore(collection=session_id)
        4. Retorna {"filename": ..., "chunks": ..., "collection_id": session_id}
        """
```

---

## Routers

### `routers/agents.py`

```python
@router.get("/agents", response_model=list[AgentInfo])
def list_agents() -> list[AgentInfo]:
    """Lista todos os agentes disponíveis com suas skills."""
```

### `routers/documents.py`

```python
@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile,
    session_id: str = "default",
    service: IngestService = Depends(get_ingest_service),
) -> UploadResponse:
    """Recebe um PDF e ingere no ChromaDB da sessão."""
```

### `routers/chat.py` — mudança no endpoint

```python
@router.post("/chat")
def chat(
    request: ChatRequest,          # agora tem agent_id
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    ...
```

---

## Dependencies — `dependencies.py`

```python
def get_agent(agent_id: str = "doc-analyst", session_id: str = "default") -> ConfigurableAgent:
    config = AGENT_REGISTRY[agent_id]
    # Verifica se existe collection da sessão no ChromaDB
    collection = session_id if collection_exists(session_id) else DEFAULT_COLLECTION
    return ConfigurableAgent(config, session_collection=collection).build()

def get_ingest_service() -> IngestService:
    return IngestService()
```

---

## UI — mudanças em `ui.py`

### Loading state

```python
# Ao enviar mensagem, exibe spinner até o primeiro evento SSE
with st.chat_message("assistant"):
    with st.spinner("Pensando..."):
        # loop SSE — spinner some quando chega o primeiro chunk
```

### Seleção de agente

```python
# Sidebar: busca GET /agents e exibe cards/dropdown
agents = httpx.get(f"{API_URL}/agents").json()
selected = st.sidebar.selectbox("Agente", [a["name"] for a in agents])
```

### Upload de documento

```python
# Sidebar ou acima do input
uploaded = st.file_uploader("📎 Carregar PDF", type=["pdf"])
if uploaded:
    httpx.post(f"{API_URL}/documents/upload",
               files={"file": uploaded},
               params={"session_id": session_id})
    st.success(f"✅ {uploaded.name} carregado")
```

---

## Plano TDD

| Arquivo de teste | Camada | O que valida |
|---|---|---|
| `test_skills.py` | Skills | `as_tool()`, nome, ícone, protocol |
| `test_agent_registry.py` | Registry | configs, skill_names válidos |
| `test_configurable_agent.py` | ConfigurableAgent | tools dinâmicas, prompt com skills |
| `test_ingest_service.py` | IngestService | ingestão de bytes, collection_id |
| `test_agents_router.py` | `GET /agents` | lista agentes, formato AgentInfo |
| `test_documents_router.py` | `POST /documents/upload` | upload, delegação ao service |
| `test_chat_router_v2.py` | Chat v2 | agent_id no request, agent selecionado |

---

## Princípios aplicados

| Princípio | Onde |
|---|---|
| **OCP** | Adicionar skill = novo arquivo em `skills/`, sem tocar em código existente |
| **SRP** | `IngestService` cuida só de ingestão; `ChatService` só de conversação |
| **DIP** | `ConfigurableAgent` depende do protocolo `Skill`, não de implementações |
| **Registry Pattern** | `AGENT_REGISTRY` centraliza a configuração de agentes |
| **Session isolation** | Cada sessão tem sua própria coleção ChromaDB quando faz upload |
