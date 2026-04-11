# Módulo: LangGraph / Agente

**Paths:** `src/docagent/base_agent.py`, `src/docagent/agents/`, `src/docagent/skills/`
**Fases:** 2, 3, 5, 6

---

## StateGraph

```
START → agent_node → [should_continue?]
                        ├─ tools_node → agent_node  (loop ReAct)
                        └─ summarize_node → END
```

**AgentState:**
```python
messages: list[BaseMessage]
summary: str   # histórico comprimido pelo summarize_node
```

---

## BaseAgent (Template Method)

`base_agent.py` define o contrato. Subclasses implementam `tools` e `system_prompt`.

```python
class BaseAgent(ABC):
    @property
    @abstractmethod
    def tools(self) -> list: ...

    @property
    @abstractmethod
    def system_prompt(self) -> str: ...

    def build(self) -> CompiledGraph: ...
```

---

## ConfigurableAgent

Monta tools + system prompt dinamicamente a partir de `AgentConfig` (carregado do banco).

```python
class ConfigurableAgent(BaseAgent):
    def __init__(self, config, system_prompt_override=None, extra_tools=None):
        self._config = config
        self._system_prompt_override = system_prompt_override
        self._extra_tools = extra_tools or []

    @property
    def tools(self) -> list:
        built_in = [SKILL_REGISTRY[name].as_tool()
                    for name in self._config.skill_names
                    if name in SKILL_REGISTRY]
        return built_in + self._extra_tools   # built-in + MCP tools
```

---

## SKILL_REGISTRY

```python
SKILL_REGISTRY = {
    "rag_search": RagSearchSkill(),
    "web_search": WebSearchSkill(),
    "human_handoff": HumanHandoffSkill(),
}
```

Skills MCP não entram no registry — chegam via `extra_tools` (carregadas em runtime via stdio).
Convenção de nome MCP: `mcp:{server_id}:{tool_name}`.

---

## Memória

- **Trim:** mantém as últimas N mensagens antes de chamar o LLM
- **Summarize:** `summarize_node` comprime o histórico quando ultrapassa o limite em um campo `summary`
- O `summary` é injetado no system prompt da próxima chamada
- **Sessões:** `SessionManager` mantém o estado em memória (dict). Migração para banco planejada na Fase 19.

---

## Modelos LLM

- **Default:** Ollama local (`qwen2.5:7b`)
- **Embeddings:** `nomic-embed-text` via Ollama
- **Override por tenant:** `SystemConfig.llm_provider / llm_model / llm_api_key` (configurável na UI, Fase ~16)
- **Criptografia da API key:** pendente (Fase 21)
