---
name: asyncexitstack-mcp
description: Por que AsyncExitStack envolve o generator de streaming, não só a inicialização dos subprocessos MCP
type: feedback
---

# Decisão: AsyncExitStack dentro do managed_stream generator

**Regra:** O `async with stack:` deve estar **dentro** do generator `managed_stream()`, não fora dele.

**Why:** Subprocessos MCP (stdio) precisam estar vivos enquanto o LangGraph está processando e enviando chunks SSE. Se o `AsyncExitStack` for encerrado antes do último chunk, as chamadas às tools MCP intermediárias falham com `BrokenPipeError` ou timeout.

```python
# ERRADO — encerra subprocessos antes do stream terminar
async with stack:
    mcp_tools = await load_mcp_tools(...)
return StreamingResponse(stream_generator())

# CORRETO — subprocessos vivem durante todo o stream
async def managed_stream():
    async with stack:
        for chunk in service.stream(...):
            yield chunk

return StreamingResponse(managed_stream())
```

**How to apply:** Qualquer novo canal (além de WhatsApp/Telegram) que use MCP precisa seguir o mesmo padrão. Se um canal não usa SSE, o `AsyncExitStack` pode ser usado normalmente com `await` — mas para SSE é obrigatório estar no generator.
