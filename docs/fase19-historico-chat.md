# Fase 19 — Persistência de Histórico de Chat

## Objetivo

Persistir o histórico de conversas no banco de dados. Hoje o `SessionManager` guarda o histórico em memória — um restart do container apaga tudo. Com esta fase, o histórico sobrevive a restarts, fica acessível no frontend como sidebar de conversas e serve de base para features futuras (fine-tuning, analytics).

---

## Problema atual

```python
# session.py — hoje
class SessionManager:
    _sessions: dict[str, list[BaseMessage]] = {}  # só em memória

    def get_history(self, session_id: str) -> list[BaseMessage]: ...
    def save_history(self, session_id: str, messages: list) -> None: ...
```

Se o container api reiniciar: **todo histórico perdido**. Com múltiplas réplicas: cada worker tem seu próprio dict, sessões não são compartilhadas.

---

## Schema — Novas Tabelas

### `conversa`

```python
class Conversa(Base):
    __tablename__ = "conversa"

    id: int (PK)
    tenant_id: int (FK → tenant)
    usuario_id: int (FK → usuario)
    agente_id: int (FK → agente)
    titulo: str | None          # gerado pelo LLM no 1º turn (ex: "Análise do contrato X")
    created_at: datetime
    updated_at: datetime        # atualizado a cada nova mensagem
    arquivada: bool = False     # soft delete — não aparece na lista mas não é apagada
```

### `mensagem_conversa`

```python
class MensagemConversa(Base):
    __tablename__ = "mensagem_conversa"

    id: int (PK)
    conversa_id: int (FK → conversa, CASCADE DELETE)
    role: MensagemRole          # user | assistant | tool
    conteudo: str (TEXT)
    tool_name: str | None       # preenchido quando role=tool
    tokens_entrada: int | None  # para analytics futuros
    tokens_saida: int | None
    created_at: datetime

class MensagemRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
```

---

## Mudanças no ChatRequest

```python
# schemas.py atual
class ChatRequest(BaseModel):
    agent_id: int
    query: str

# schemas.py novo
class ChatRequest(BaseModel):
    agent_id: int
    query: str
    conversa_id: int | None = None
    # None → cria nova conversa
    # int → retoma conversa existente
```

---

## Novos Endpoints

```
GET    /api/chat/conversas
    → Lista conversas do usuário (paginada, ordenada por updated_at DESC)
    → Params: agente_id (filtro opcional), arquivada (default False), page, page_size

GET    /api/chat/conversas/{id}
    → Conversa completa com todas as mensagens
    → Retorna ConversaDetalhada (+ lista de MensagemConversa)

DELETE /api/chat/conversas/{id}
    → Soft delete: arquivada = True (não remove do banco)

POST   /api/chat/conversas/{id}/restaurar
    → arquivada = False

POST   /api/chat  (existente — sem quebra de contrato)
    → Agora aceita conversa_id opcional
    → Se conversa_id: carrega histórico do banco antes de executar o agente
    → Ao final: persiste mensagens novas no banco
    → Resposta inclui conversa_id no header SSE ou body final
```

---

## ConversaService

```python
class ConversaService:

    async def criar(
        tenant_id: int,
        usuario_id: int,
        agente_id: int,
        db: AsyncSession
    ) -> Conversa:
        # Insere nova conversa sem título ainda

    async def get_by_id(
        conversa_id: int,
        tenant_id: int,
        db: AsyncSession
    ) -> Conversa | None:
        # Garante isolamento por tenant

    async def listar(
        usuario_id: int,
        tenant_id: int,
        agente_id: int | None,
        arquivada: bool,
        page: int,
        page_size: int,
        db: AsyncSession
    ) -> list[Conversa]:
        # SELECT ... ORDER BY updated_at DESC LIMIT page_size OFFSET ...

    async def salvar_mensagem(
        conversa_id: int,
        role: MensagemRole,
        conteudo: str,
        db: AsyncSession
    ) -> MensagemConversa:
        # INSERT + UPDATE conversa.updated_at

    async def carregar_historico(
        conversa_id: int,
        db: AsyncSession
    ) -> list[BaseMessage]:
        # SELECT mensagens → converte para HumanMessage/AIMessage/ToolMessage

    async def gerar_titulo(
        conversa_id: int,
        primeira_mensagem: str,
        llm,
        db: AsyncSession
    ) -> None:
        # Chama LLM com prompt: "Gere um título curto (max 6 palavras) para esta conversa: {msg}"
        # UPDATE conversa SET titulo = resultado

    async def arquivar(conversa_id: int, tenant_id: int, db: AsyncSession) -> None:
        # UPDATE arquivada = True

    async def restaurar(conversa_id: int, tenant_id: int, db: AsyncSession) -> None:
        # UPDATE arquivada = False
```

---

## Migração do SessionManager

O `SessionManager` atual usa `session_id` (string). A migração é compatível:

```python
# session.py — novo
class SessionManager:
    """
    Adapta a interface existente para persistência no banco.
    session_id = str(conversa_id)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_history(self, session_id: str) -> list[BaseMessage]:
        conversa_id = int(session_id)
        return await ConversaService.carregar_historico(conversa_id, self.db)

    async def save_history(
        self,
        session_id: str,
        messages: list[BaseMessage]
    ) -> None:
        conversa_id = int(session_id)
        # Salva apenas as mensagens novas (delta)
        # Compara com o que já existe no banco
```

O `ChatService` e o router `/chat` continuam funcionando sem mudanças de interface pública — só passa `db` para o `SessionManager`.

---

## Geração de Título Automático

Após o primeiro turn completo (user + assistant), dispara em background:

```python
# Após o agente responder a primeira mensagem:
if conversa.titulo is None:
    asyncio.create_task(
        ConversaService.gerar_titulo(conversa.id, user_query, llm, db)
    )
```

Prompt usado:
```
Gere um título curto (máximo 6 palavras) para uma conversa que começa com:
"{primeira_mensagem}"
Responda APENAS com o título, sem aspas, sem pontuação final.
```

---

## Frontend — Sidebar de Conversas

### ChatView.vue — melhorias

```
┌──────────────────┬────────────────────────────────────┐
│ Conversas        │                                    │
│                  │  Agente: [Assistente Jurídico ▼]   │
│ Hoje             │                                    │
│  > Análise do... │  ┌─────────────────────────────┐  │
│  > Contrato de.. │  │ Você: preciso analisar...   │  │
│                  │  │ Agente: Com base nos docs... │  │
│ Ontem            │  │                             │  │
│  > Revisão NDA   │  └─────────────────────────────┘  │
│  > Cláusula 5ª   │                                    │
│                  │  [Digite sua mensagem...] [Enviar] │
│ [+ Nova conversa]│                                    │
└──────────────────┴────────────────────────────────────┘
```

**Comportamento:**
- Sidebar lista conversas agrupadas por data (Hoje, Ontem, Esta semana, Mais antigas)
- Clicar numa conversa: carrega histórico e continua
- Botão "+ Nova conversa": cria nova (conversa_id = null no próximo POST /chat)
- Hover na conversa: ícone de arquivar (lixeira)
- Conversas arquivadas ficam em aba separada "Arquivadas"

### Paginação infinite scroll
- Carrega 20 conversas por vez
- Scroll para baixo na sidebar → `GET /api/chat/conversas?page=2`

---

## Schemas

```python
class ConversaPublic(BaseModel):
    id: int
    agente_id: int
    agente_nome: str
    titulo: str | None
    created_at: datetime
    updated_at: datetime
    total_mensagens: int

class MensagemConversaPublic(BaseModel):
    id: int
    role: MensagemRole
    conteudo: str
    created_at: datetime

class ConversaDetalhada(ConversaPublic):
    mensagens: list[MensagemConversaPublic]

class ConversaListResponse(BaseModel):
    items: list[ConversaPublic]
    total: int
    page: int
    page_size: int
    has_more: bool
```

---

## Estrutura de Arquivos

```
src/docagent/
├── conversa/
│   ├── __init__.py
│   ├── models.py      — Conversa, MensagemConversa, MensagemRole
│   ├── schemas.py     — ConversaPublic, MensagemConversaPublic, ConversaDetalhada
│   ├── services.py    — ConversaService
│   └── router.py     — GET /conversas, GET /conversas/{id}, DELETE /conversas/{id}
└── chat/
    ├── router.py      — atualizado: aceita conversa_id, persiste mensagens
    ├── service.py     — atualizado: usa ConversaService
    └── session.py     — atualizado: lê/grava no banco via ConversaService
```

---

## Testes

```
tests/test_historico/
├── conftest.py
├── test_conversa_service.py
│   ├── test_criar_conversa
│   ├── test_carregar_historico_vazio
│   ├── test_salvar_e_carregar_mensagens
│   ├── test_gerar_titulo_apos_primeiro_turn
│   ├── test_listar_paginado
│   ├── test_arquivar_e_restaurar
│   └── test_isolamento_por_tenant          — tenant A não vê conversas do tenant B
├── test_chat_router_com_historico.py
│   ├── test_nova_conversa_criada_automaticamente
│   ├── test_conversa_retomada_com_contexto
│   ├── test_conversa_inexistente_retorna_404
│   └── test_regressao_chat_sem_conversa_id  — comportamento atual ainda funciona
└── test_session_manager.py
    ├── test_get_history_do_banco
    └── test_save_history_persiste
```

---

## Ordem de Implementação

```
1.  Branch: fase-19
2.  Alembic: tabelas conversa + mensagem_conversa
3.  conversa/models.py + conversa/schemas.py
4.  🔴 RED: test_conversa_service.py
5.  🟢 GREEN: conversa/services.py
6.  🔴 RED: test_chat_router_com_historico.py
7.  🟢 GREEN: chat/session.py (migração para banco)
               chat/router.py (aceita conversa_id)
               chat/service.py (persiste mensagens)
8.  conversa/router.py (GET /conversas, etc.)
9.  api.py → registrar router conversa
10. test_session_manager.py
11. Frontend: sidebar de conversas no ChatView.vue
12. Infinite scroll + agrupamento por data
```

---

## Gotchas

- **Delta de mensagens:** ao salvar, não re-inserir mensagens que já existem no banco. Comparar pelo índice ou usar flag `persistida` nas mensagens em memória durante o turn.
- **Título nulo na UI:** enquanto o LLM não gera o título, exibir "Nova conversa" como placeholder.
- **Conversa de outro tenant:** `GET /api/chat/conversas/{id}` deve validar `tenant_id` — nunca expor conversa de outro tenant.
- **Agente deletado:** se `agente_id` foi deletado após a conversa, `ConversaPublic.agente_nome` retorna `"[Agente removido]"` sem quebrar a query.
- **Summarize node:** o LangGraph hoje sumariza mensagens antigas e descarta originais. Com persistência, salvar o summary como mensagem de role `system` na conversa para referência.
