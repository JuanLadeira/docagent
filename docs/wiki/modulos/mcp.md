# Módulo: mcp_server/

**Path:** `src/docagent/mcp_server/`
**Fase:** 11
**Transporte:** stdio apenas (subprocesso local)

---

## Responsabilidade

Permitir que o operador registre servidores MCP via UI, descubra suas tools e as selecione como skills de um agente — sem escrever código Python.

---

## Modelos

```python
class McpServer(Base):
    __tablename__ = "mcp_server"
    nome, descricao: str
    command: str        # ex: "npx"
    args: list          # JSON: ["-y", "@modelcontextprotocol/server-filesystem", "/path"]
    env: dict           # JSON: env vars para o subprocesso
    ativo: bool

class McpTool(Base):
    __tablename__ = "mcp_tool"
    server_id: FK → McpServer (CASCADE DELETE)
    tool_name: str
    description: str
```

---

## Convenção de Skill

```
mcp:{server_id}:{tool_name}
```

Exemplos: `"mcp:1:read_file"`, `"mcp:2:list_issues"`
Skills built-in não têm prefixo: `"rag_search"`, `"web_search"`.

---

## Ciclo de Vida dos Subprocessos

**Problema:** O subprocess stdio precisa ficar ativo durante todo o streaming SSE do chat.

**Solução:** `AsyncExitStack` envolve o generator:

```python
async def managed_stream():
    async with stack:           # subprocessos vivos aqui
        for chunk in service.stream(...):
            yield chunk
    # subprocessos encerrados aqui (fim do stream)
```

Ver [decisao: asyncexitstack-mcp](../decisoes/asyncexitstack-mcp.md).

---

## Endpoints

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/api/mcp-servidores/` | Lista servidores |
| POST | `/api/mcp-servidores/` | Registra servidor |
| PUT | `/api/mcp-servidores/{id}` | Atualiza |
| DELETE | `/api/mcp-servidores/{id}` | Remove (CASCADE tools) |
| POST | `/api/mcp-servidores/{id}/descobrir-tools` | Conecta stdio, salva tools no banco |
| GET | `/api/mcp-servidores/{id}/tools` | Lista tools (lê do banco, sem conexão) |

---

## Servidores Compatíveis (exemplos)

| Servidor | command | args |
|----------|---------|------|
| Filesystem | `npx` | `["-y", "@modelcontextprotocol/server-filesystem", "/path"]` |
| GitHub | `npx` | `["-y", "@modelcontextprotocol/server-github"]` |
| PostgreSQL | `npx` | `["-y", "@modelcontextprotocol/server-postgres", "postgresql://..."]` |
| Python custom | `uvx` | `["meu-mcp-server"]` |
