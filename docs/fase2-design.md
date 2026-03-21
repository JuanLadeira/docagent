# Fase 2 — Design do Agente com LangGraph

## O padrão: ReAct Loop

A Fase 2 implementa o padrão **ReAct** (Reason + Act), o ciclo fundamental de todo agente de IA:

```
Reason  →  o LLM analisa a pergunta e decide qual ferramenta usar
Act     →  a ferramenta é executada
Observe →  o LLM recebe o resultado e decide: responde ou busca mais?
Repeat  →  repete até ter informação suficiente para responder
```

Na Fase 1 o fluxo era linear e fixo: `pergunta → RAG → LLM → resposta`. Agora o LLM toma decisões.

---

## O Grafo

```
         START
           │
           ▼
    ┌─────────────┐
    │  agent node │  ← LLM com tools vinculadas
    └─────────────┘
           │
    ┌──────┴──────────────────────┐
    │ tem tool_calls na resposta? │  ← aresta condicional
    └──────┬──────────────────────┘
           │                    │
          SIM                  NÃO
           │                    │
           ▼                    ▼
    ┌─────────────┐           END
    │ tools node  │
    └─────────────┘
           │
           │  resultado da tool
           │
           └──────────────────► agent node  (loop)
```

---

## Os dois nós

**`agent` node**
- Recebe o histórico de mensagens completo (estado)
- Chama o LLM (`qwen2.5:7b`) com as tools vinculadas via `.bind_tools()`
- O LLM retorna uma `AIMessage` que pode conter zero ou mais `tool_calls`
- Não executa nada — só decide

**`tools` node**
- Recebe os `tool_calls` da mensagem anterior
- Executa cada tool chamada (RAG ou web)
- Retorna `ToolMessage` com o resultado
- Nunca decide nada — só executa

---

## O Estado

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
```

O estado é **apenas a lista de mensagens**. Cada nó lê o estado, adiciona sua mensagem e passa adiante. O `add_messages` é um reducer que faz append em vez de sobrescrever — essencial para o loop funcionar.

O histórico completo fica assim após duas iterações:

```
HumanMessage      → pergunta do usuário
AIMessage         → LLM decide usar rag_search (tool_call)
ToolMessage       → resultado do RAG
AIMessage         → LLM decide usar web_search (tool_call)
ToolMessage       → resultado da web
AIMessage         → LLM responde com base em ambos (sem tool_call → END)
```

---

## As duas Tools

| Tool | Quando o LLM deve escolher |
|---|---|
| `rag_search(query)` | Pergunta sobre os documentos carregados |
| `web_search(query)` | Pergunta que precisa de informação atual ou externa |

As tools são funções Python decoradas com `@tool` do LangChain. O LLM aprende quando usar cada uma pela **descrição da tool** — isso é crítico: descrição ruim = tool escolhida errada.

---

## A aresta condicional

```python
def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"   # continua o loop
    return END           # responde ao usuário
```

Essa função é chamada após cada execução do `agent` node. É ela que implementa o loop — sem ela o grafo seria linear igual à Fase 1.

---

## Estrutura de arquivos

```
src/docagent/
├── agent.py       ← StateGraph + nós + aresta condicional
└── tools.py       ← @tool rag_search + @tool web_search  (arquivo novo)
```

`tools.py` separado de `agent.py` porque na Fase 3 vamos reusar as tools sem instanciar o grafo inteiro.
