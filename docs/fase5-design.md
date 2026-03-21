# Fase 5 — Design OOP: BaseAgent, SessionManager e Arquitetura em Camadas

## Objetivo

Refatorar o código funcional das fases anteriores para:
1. Hierarquia OOP com `BaseAgent` reutilizável
2. Arquitetura em camadas: schemas → services → routers
3. Injeção de dependência via FastAPI `Depends`

Os 81 testes existentes são preservados. Novos testes cobrem cada camada.

---

## Estrutura de arquivos

```
src/docagent/
├── base_agent.py          ← BaseAgent ABC + _build_graph()
├── doc_agent.py           ← DocAgent(BaseAgent)
├── session.py             ← SessionManager
│
├── schemas/
│   ├── __init__.py
│   └── chat.py            ← ChatRequest, HealthResponse (Pydantic)
│
├── services/
│   ├── __init__.py
│   └── chat_service.py    ← ChatService: orquestra agente + sessão
│
├── routers/
│   ├── __init__.py
│   └── chat.py            ← endpoints FastAPI com Depends
│
├── dependencies.py        ← get_agent(), get_session_manager()
├── api.py                 ← FastAPI app assembly (registra routers)
└── memory.py              ← sem mudanças
```

---

## Camada de schemas — `schemas/chat.py`

Define contratos de entrada e saída da API. Sem lógica de negócio.

```python
class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"

    @field_validator("question")
    def question_must_not_be_empty(cls, v): ...

class HealthResponse(BaseModel):
    status: str
```

---

## Camada de services — `services/chat_service.py`

Orquestra o agente e o gerenciador de sessão. Sem conhecimento de HTTP.

```python
class ChatService:
    def __init__(self, agent: BaseAgent, session_manager: SessionManager):
        self.agent = agent
        self.session_manager = session_manager

    def stream(self, question: str, session_id: str) -> Iterator[str]:
        state = self.session_manager.get(session_id)
        final_state = None
        for event in self.agent.stream(question, state):
            if '"type": "done"' not in event:
                final_state = ...  # captura estado interno do agente
            yield event
        if final_state:
            self.session_manager.update(session_id, final_state)

    def delete_session(self, session_id: str) -> bool:
        return self.session_manager.delete(session_id)
```

---

## Dependências — `dependencies.py`

Funções que o FastAPI injeta via `Depends`. Usam `lru_cache` para garantir
uma única instância por processo (singleton via cache).

```python
from functools import lru_cache

@lru_cache(maxsize=1)
def get_agent() -> DocAgent:
    return DocAgent().build()

@lru_cache(maxsize=1)
def get_session_manager() -> SessionManager:
    return SessionManager()

def get_chat_service(
    agent: DocAgent = Depends(get_agent),
    sessions: SessionManager = Depends(get_session_manager),
) -> ChatService:
    return ChatService(agent, sessions)
```

---

## Camada de routers — `routers/chat.py`

Endpoints HTTP. Sem lógica de negócio — delega tudo ao `ChatService`.

```python
router = APIRouter()

@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")

@router.post("/chat")
def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    return StreamingResponse(
        service.stream(request.question, request.session_id),
        media_type="text/event-stream",
    )

@router.delete("/session/{session_id}")
def delete_session(
    session_id: str,
    service: ChatService = Depends(get_chat_service),
) -> dict:
    if not service.delete_session(session_id):
        raise HTTPException(status_code=404, ...)
    return {"status": "cleared", "session_id": session_id}
```

---

## App assembly — `api.py` (simplificado)

```python
app = FastAPI(title="DocAgent API")
app.include_router(chat_router)
```

---

## BaseAgent — Template Method pattern

```python
class BaseAgent(ABC):
    def __init__(self):
        self._graph = None

    @property
    @abstractmethod
    def tools(self) -> list: ...

    @property
    @abstractmethod
    def system_prompt(self) -> str: ...

    def build(self) -> "BaseAgent":
        self._graph = _build_graph(self.tools, self.system_prompt)
        return self

    def run(self, question: str, state: dict | None = None) -> dict:
        if self._graph is None:
            raise RuntimeError("Chame build() antes de run().")
        ...

    def stream(self, question: str, state: dict | None = None) -> Iterator[str]:
        if self._graph is None:
            raise RuntimeError("Chame build() antes de stream().")
        ...
```

---

## SessionManager

```python
class SessionManager:
    def __init__(self):
        self._sessions: dict[str, dict] = {}

    def get(self, session_id: str) -> dict:
        return self._sessions.get(session_id, {"messages": [], "summary": ""})

    def update(self, session_id: str, state: dict) -> None:
        self._sessions[session_id] = state

    def delete(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def has(self, session_id: str) -> bool:
        return session_id in self._sessions

    def clear(self) -> None:
        self._sessions.clear()
```

---

## Princípios aplicados

| Princípio | Onde |
|---|---|
| **SRP** | Cada camada tem uma responsabilidade única |
| **OCP** | Novo agente = nova subclasse, sem tocar em api.py ou service |
| **LSP** | DocAgent é substituível por qualquer BaseAgent no ChatService |
| **DIP** | Routers dependem de ChatService (abstração), não de DocAgent |
| **FastAPI Depends** | Dependências declaradas na assinatura, testáveis por override |

---

## Plano TDD

| Arquivo de teste | Camada | O que valida |
|---|---|---|
| `test_base_agent.py` | BaseAgent | ABC, build(), run(), stream() |
| `test_doc_agent.py` | DocAgent | tools, system_prompt, herança |
| `test_session.py` | SessionManager | get/update/delete/has/clear |
| `test_chat_service.py` | ChatService | stream SSE, atualização de sessão, delete |
| `test_routers.py` | Routers + Depends | endpoints com dependências sobrescritas |
