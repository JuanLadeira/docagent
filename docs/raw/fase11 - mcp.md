# Fase 11 — MCP: Skills Dinâmicas via Model Context Protocol

## Objetivo

Integrar o [Model Context Protocol (MCP)](https://modelcontextprotocol.io) ao DocAgent para que o operador possa registrar servidores MCP e expor suas tools como skills selecionáveis no CRUD de agentes — sem escrever código Python nem reimplantar o sistema.

Pré-requisito: **Fase 10 concluída** (Frontend Vue.js + CRUD de agentes).

---

## Problema Atual

O `SKILL_REGISTRY` é hardcoded em Python:

```python
SKILL_REGISTRY: dict = {
    "rag_search": RagSearchSkill(),
    "web_search": WebSearchSkill(),
}
```

Adicionar uma nova skill exige:
1. Escrever uma classe Python
2. Registrar no `SKILL_REGISTRY`
3. Reimplantar o container

Com MCP, o fluxo passa a ser:
1. Registrar o servidor MCP no banco via UI
2. Clicar em "Descobrir Tools"
3. Selecionar as tools desejadas ao criar/editar um agente

---

## Suporte de Transporte

Apenas **`stdio`** (subprocesso local):
- O servidor MCP roda como subprocesso do container da API
- Comandos como `npx -y @modelcontextprotocol/server-filesystem /docs`
- Aplicável a qualquer servidor MCP disponível no PATH do container

---

## Modelos de Dados

**`src/docagent/mcp_server/models.py`**

```python
class McpServer(Base):
    __tablename__ = "mcp_server"

    nome: Mapped[str]         # display name (ex: "Filesystem")
    descricao: Mapped[str]
    command: Mapped[str]      # ex: "npx"
    args: Mapped[list]        # JSON: ["-y", "@modelcontextprotocol/server-filesystem", "/path"]
    env: Mapped[dict]         # JSON: env vars adicionais para o subprocesso
    ativo: Mapped[bool]


class McpTool(Base):
    __tablename__ = "mcp_tool"

    server_id: Mapped[int]    # FK -> McpServer (CASCADE DELETE)
    tool_name: Mapped[str]    # nome original da tool (ex: "read_file")
    description: Mapped[str]  # descrição retornada pelo servidor
```

### Convenção de nome de skill MCP

Skills MCP são armazenadas em `Agente.skill_names` com o prefixo `mcp:`:

```
mcp:{server_id}:{tool_name}
```

Exemplos:
- `"mcp:1:read_file"`
- `"mcp:1:list_directory"`
- `"mcp:2:list_issues"`

Skills built-in continuam sem prefixo: `"rag_search"`, `"web_search"`.

---

## Endpoints Backend

**Prefixo: `/api/mcp-servidores`**

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| GET | `/` | User | Lista todos os servidores registrados |
| POST | `/` | Owner | Registra novo servidor |
| PUT | `/{id}` | Owner | Atualiza servidor |
| DELETE | `/{id}` | Owner | Remove servidor e suas tools (CASCADE) |
| POST | `/{id}/descobrir-tools` | Owner | Conecta via stdio, descobre tools e salva em `McpTool` |
| GET | `/{id}/tools` | User | Lista tools descobertas (lê do banco, sem conexão) |

---

## Arquitetura de Runtime

### Problema

O subprocesso stdio do MCP precisa ficar ativo durante **todo** o streaming do chat. Se o contexto for fechado antes, as chamadas às tools falham.

### Solução: `AsyncExitStack` envolvendo o generator

O `AsyncExitStack` gerencia o ciclo de vida dos subprocessos. O generator de streaming só termina (e os processos são encerrados) quando o último chunk SSE é entregue ao cliente.

```
POST /chat
  │
  ├─ Carrega Agente do banco
  ├─ Separa skill_names em built-in vs mcp:*
  ├─ Cria AsyncExitStack
  ├─ Para cada server_id único nos mcp:*:
  │    ├─ stack.enter_async_context(stdio_client(...))  ← inicia subprocesso
  │    └─ stack.enter_async_context(ClientSession(...)) ← handshake MCP
  ├─ ConfigurableAgent(config, extra_tools=mcp_tools).build()
  └─ managed_stream():
       async with stack:   ← subprocessos vivos aqui
           for chunk in service.stream(...):
               yield chunk
       ← subprocessos encerrados aqui (fim do stream)
```

### Implementação em `routers/chat.py`

```python
from contextlib import AsyncExitStack

@router.post("/chat")
async def chat(request, agente_service, mcp_service, sessions):
    agente = await agente_service.get_by_id(int(request.agent_id))

    mcp_skill_names = [n for n in agente.skill_names if n.startswith("mcp:")]
    stack = AsyncExitStack()
    mcp_tools = []

    if mcp_skill_names:
        servers = await mcp_service.get_all(apenas_ativos=True)
        mcp_tools = await load_mcp_tools_for_skills(mcp_skill_names, servers, stack)

    config = AgentConfig(id=str(agente.id), name=agente.nome,
                         description=agente.descricao, skill_names=agente.skill_names)
    agent = ConfigurableAgent(config, extra_tools=mcp_tools,
                              system_prompt_override=agente.system_prompt).build()
    service = ChatService(agent, sessions)

    async def managed_stream():
        async with stack:
            for chunk in service.stream(request.question, request.session_id):
                yield chunk

    return StreamingResponse(managed_stream(), media_type="text/event-stream", ...)
```

### `load_mcp_tools_for_skills()` em `mcp_server/services.py`

```python
async def load_mcp_tools_for_skills(skill_names, servers, stack):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from langchain_mcp_adapters.tools import load_mcp_tools

    # Agrupar tool_names por server_id
    by_server: dict[str, list[str]] = {}
    for name in skill_names:
        _, sid, tname = name.split(":", 2)
        by_server.setdefault(sid, []).append(tname)

    tools = []
    for sid, tool_names in by_server.items():
        server = next((s for s in servers if str(s.id) == sid), None)
        if not server or not server.ativo:
            continue
        params = StdioServerParameters(
            command=server.command,
            args=server.args,
            env=server.env or None,
        )
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        all_tools = await load_mcp_tools(session)
        tools += [t for t in all_tools if t.name in tool_names]

    return tools
```

---

## Mudanças em Arquivos Existentes

| Arquivo | Mudança |
|---------|---------|
| `pyproject.toml` | Adicionar `mcp` e `langchain-mcp-adapters` |
| `agents/configurable_agent.py` | `__init__` recebe `extra_tools: list = []`; `tools` property retorna built-in + extra_tools |
| `routers/chat.py` | AsyncExitStack + `load_mcp_tools_for_skills()` |
| `routers/agents.py` | `GET /agents` inclui tools MCP de cada agente (lê `McpTool` do banco) |
| `api.py` | Registrar `mcp_server_router` |
| `compose/entrypoint.sh` | `Base.metadata.create_all` já cobre as novas tabelas |

### `configurable_agent.py` após a mudança

```python
class ConfigurableAgent(BaseAgent):
    def __init__(self, config, system_prompt_override=None, extra_tools=None):
        super().__init__()
        self._config = config
        self._system_prompt_override = system_prompt_override
        self._extra_tools = extra_tools or []

    @property
    def tools(self) -> list:
        built_in = [
            SKILL_REGISTRY[name].as_tool()
            for name in self._config.skill_names
            if name in SKILL_REGISTRY
        ]
        return built_in + self._extra_tools
```

---

## Frontend

### Nova view: `McpServidoresView.vue` (`/mcp-servidores`)

- Tabela de servidores cadastrados com badge de status (ativo/inativo)
- Contagem de tools descobertas por servidor
- Modal de criação/edição:
  - Nome e descrição
  - Command (ex: `npx`)
  - Args — uma por linha (textarea)
  - Env — JSON (textarea, opcional)
  - Toggle ativo/inativo
- Botão "Descobrir Tools" por servidor:
  - Chama `POST /api/mcp-servidores/{id}/descobrir-tools`
  - Exibe lista de tools encontradas em dropdown expansível
- Disponível apenas para OWNER no nav lateral

### Update: `AgentesView.vue`

O seletor de skills passa a ter duas seções:

```
Skills Nativas
  [x] 🔍 Busca em Documentos (rag_search)
  [x] 🌐 Busca na Web (web_search)

MCP: Filesystem
  [ ] read_file — Read the complete contents of a file
  [x] list_directory — Get a listing of all files in a directory

MCP: GitHub
  [ ] list_issues — List issues for a repository
  [ ] create_issue — Create a new issue
```

- Carregado via `GET /api/mcp-servidores/{id}/tools` (lê do banco, sem conexão)
- Skill names salvas no formato `mcp:{server_id}:{tool_name}`
- Se nenhum servidor MCP estiver registrado, a seção não aparece

### Novos tipos em `client.ts`

```typescript
interface McpServer {
  id: number
  nome: string
  descricao: string
  command: string
  args: string[]
  env: Record<string, string>
  ativo: boolean
  created_at: string
  updated_at: string
}

interface McpTool {
  id: number
  server_id: number
  tool_name: string
  description: string
}
```

### Novos endpoints em `client.ts`

```typescript
api.listMcpServidores()                    // GET /api/mcp-servidores/
api.createMcpServidor(data)                // POST /api/mcp-servidores/
api.updateMcpServidor(id, data)            // PUT /api/mcp-servidores/{id}
api.deleteMcpServidor(id)                  // DELETE /api/mcp-servidores/{id}
api.descobrirTools(id)                     // POST /api/mcp-servidores/{id}/descobrir-tools
api.listMcpTools(id)                       // GET /api/mcp-servidores/{id}/tools
```

---

## Ordem de Implementação

1. `uv add mcp langchain-mcp-adapters`
2. Criar `src/docagent/mcp_server/` (models, schemas, services, router)
3. Registrar router em `api.py`
4. Atualizar `ConfigurableAgent` (`extra_tools`)
5. Atualizar `routers/chat.py` (AsyncExitStack lifecycle)
6. Atualizar `routers/agents.py` (incluir MCP tools no AgentInfo)
7. Frontend: `McpServidoresView.vue`
8. Frontend: atualizar `AgentesView.vue` com seção MCP
9. Frontend: rota + nav link

---

## Verificação End-to-End

```bash
# 1. Instalar dependências e rebuild
uv add mcp langchain-mcp-adapters
docker compose up --build api -d

# 2. Registrar servidor MCP Filesystem
curl -X POST http://localhost:8000/api/mcp-servidores/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "nome": "Filesystem",
    "descricao": "Acesso a arquivos locais",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
    "env": {},
    "ativo": true
  }'

# 3. Descobrir tools
curl -X POST http://localhost:8000/api/mcp-servidores/1/descobrir-tools \
  -H "Authorization: Bearer <token>"
# Esperado: [{"tool_name": "read_file", ...}, {"tool_name": "list_directory", ...}]

# 4. Criar agente com tools MCP
curl -X POST http://localhost:8000/api/agentes/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "nome": "File Agent",
    "descricao": "Lê e lista arquivos locais",
    "skill_names": ["mcp:1:read_file", "mcp:1:list_directory"],
    "ativo": true
  }'

# 5. Chat com agente MCP
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Liste os arquivos em /tmp",
    "session_id": "test",
    "agent_id": "3"
  }'
# O agente deve invocar list_directory e retornar os arquivos

# 6. Verificar que o subprocesso encerra após o stream
#    (não deve haver processos npx órfãos após a resposta)
ps aux | grep modelcontextprotocol  # deve estar vazio
```

---

## Exemplos de Servidores MCP Compatíveis

| Servidor | Command | Args |
|----------|---------|------|
| Filesystem | `npx` | `["-y", "@modelcontextprotocol/server-filesystem", "/caminho"]` |
| GitHub | `npx` | `["-y", "@modelcontextprotocol/server-github"]` |
| PostgreSQL | `npx` | `["-y", "@modelcontextprotocol/server-postgres", "postgresql://..."]` |
| Fetch (HTTP) | `npx` | `["-y", "@modelcontextprotocol/server-fetch"]` |
| Qualquer servidor Python | `uvx` | `["meu-mcp-server"]` |
