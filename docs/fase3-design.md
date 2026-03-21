# Fase 3 — Design da Memória

## O problema que a Fase 3 resolve

O agente da Fase 2 é **amnésico** — cada pergunta começa do zero. Se você perguntar
"o que é RAG?" e depois "quais são suas vantagens?", o agente não sabe que "suas" se
refere a RAG. Isso torna conversas multi-turno impossíveis.

---

## Os três tipos de memória

```
Curto prazo (In-Context)         Longo prazo (External)
────────────────────────         ──────────────────────
[msg1][msg2][msg3]...            ChromaDB / banco relacional
Tudo no prompt — simples         Recuperado por busca semântica
Limitado pelo context window     Ilimitado, mas precisa de retrieval
```

**ConversationSummaryBufferMemory** é o meio-termo:

```
HISTÓRICO ANTIGO         MENSAGENS RECENTES
(resumido pelo LLM)  +   (completas, verbatim)
─────────────────────    ──────────────────────────────────
"O usuário perguntou     [HumanMessage: "e os embeddings?"]
sobre RAG e o agente     [AIMessage: "Embeddings são..."]
explicou o pipeline"     [HumanMessage: "qual o tamanho?"]
                         [AIMessage: "768 dimensões..."]
```

---

## Como integrar ao LangGraph

O estado do agente ganha um novo campo:

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    summary:  str   # resumo do histórico antigo — novo campo
```

O grafo ganha um terceiro nó:

```
         START
           │
           ▼
    ┌─────────────┐
    │  agent node │  ← recebe summary + mensagens recentes no prompt
    └─────────────┘
           │
    ┌──────┴──────────────────────┐
    │   tem tool_calls?           │
    └──────┬──────────────────────┘
           │                    │
          SIM                  NÃO
           │                    │
           ▼                    ▼
    ┌─────────────┐    ┌──────────────────┐
    │ tools node  │    │ summarize node   │  ← novo nó
    └─────────────┘    └──────────────────┘
           │                    │
           └──── agent node     ▼
                              END
```

---

## Os três nós

**`agent node` (atualizado)**
- Verifica se existe `state["summary"]`
- Se sim, injeta o resumo como contexto no início das mensagens
- Comportamento idêntico à Fase 2 no restante

**`tools node`** (sem mudança)
- Executa as tools chamadas pelo LLM
- Retorna ToolMessage com resultado

**`summarize node`** (novo)
- Executado toda vez que o LLM responde sem tool_calls (fim de turno)
- Verifica se o número de mensagens ultrapassou o threshold (padrão: 6)
- Se sim: chama o LLM para condensar o histórico antigo + resumo anterior
- Trunca as mensagens antigas, mantém só as N mais recentes (padrão: 2)
- Salva o novo resumo em `state["summary"]`
- Se não: passa direto para END sem resumir

---

## O prompt de resumo

```
Faça um resumo conciso da conversa abaixo em português.
Se já existe um resumo anterior, estenda-o com as novas informações.

Resumo atual:
{summary_existente}

Novas mensagens:
{mensagens_antigas}

Resumo atualizado:
```

---

## Injeção do resumo no agent node

```
SystemMessage: <instrução de usar tools em português>
HumanMessage:  [CONTEXTO DA CONVERSA ANTERIOR]
               {summary}
HumanMessage:  nova pergunta do usuário
```

O resumo é injetado como uma `HumanMessage` separada antes da pergunta atual,
mantendo o formato de chat válido para o `ChatOllama`.

---

## Por que threshold e não resumir sempre?

Resumir a cada turno seria desperdiçar tokens e latência. O threshold (padrão: 6
mensagens) garante que:
- Conversas curtas não sofrem overhead de uma chamada extra ao LLM
- Conversas longas não estouram o context window do `qwen2.5:7b` (32k tokens)

O threshold e o número de mensagens recentes mantidas são configuráveis via `.env`.

---

## Estrutura de arquivos

```
src/docagent/
├── memory.py   ← lógica de resumo: should_summarize() e summarize_history()
└── agent.py    ← atualizado: novo campo no state + summarize node + injeção do resumo
```

`memory.py` separado de `agent.py` para isolar e testar a lógica de resumo
independentemente do grafo.

---

## Por que não usar ConversationSummaryBufferMemory diretamente?

A classe `ConversationSummaryBufferMemory` do LangChain foi projetada para chains,
não para grafos com estado. No LangGraph, o estado é explícito — é mais limpo e mais
educativo implementar o mesmo padrão manualmente como um nó do grafo, do que adaptar
uma abstração que não foi feita para esse modelo mental.
