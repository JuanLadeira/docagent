# Fase 4 — Design de API, Observabilidade e UI

## Visao geral

A Fase 4 empacota o agente das fases anteriores em tres camadas:

```
[Streamlit UI]  →  HTTP/SSE  →  [FastAPI]  →  [LangGraph Agent]
                                     ↓
                               [LangSmith]  ← rastreamento de cada passo
```

O Ollama continua rodando nativamente (fora do Docker).
Apenas FastAPI e Streamlit sao containerizados.

---

## FastAPI — `src/docagent/api.py`

### Endpoints

| Metodo | Rota | Descricao |
|---|---|---|
| `GET` | `/health` | Verifica se a API esta no ar |
| `POST` | `/chat` | Envia uma pergunta e recebe resposta em streaming SSE |
| `DELETE` | `/session/{session_id}` | Limpa o historico de uma sessao |

### Modelo de request

```python
class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"
```

### SSE — formato dos eventos

Cada evento segue o formato padrao SSE:

```
data: {"type": "step", "content": "Tool Calls: rag_search..."}

data: {"type": "answer", "content": "RAG e uma tecnica..."}

data: {"type": "done"}
```

- `step`: cada mensagem intermediaria do grafo (tool calls, tool results)
- `answer`: a resposta final do agente
- `done`: sinaliza fim do stream — o cliente pode fechar a conexao

### Gerenciamento de sessao

```python
sessions: dict[str, dict] = {}  # session_id -> AgentState
```

O estado do agente (messages + summary) e mantido em memoria por sessao.
Isso permite conversas multi-turno via API sem reenviar o historico completo.

O `session_id` e gerado pelo cliente (ex: UUID). A API cria a sessao
automaticamente na primeira requisicao com aquele ID.

### Streaming com SSE

```
POST /chat
  ↓
Cria/recupera sessao
  ↓
Roda graph.stream(state, stream_mode="values")
  ↓
Para cada passo → yield SSE event ("step")
  ↓
Ultima mensagem → yield SSE event ("answer")
  ↓
yield SSE event ("done")
  ↓
Atualiza sessao com estado final
```

---

## LangSmith — observabilidade

LangSmith rastreia cada passo do agente: qual tool foi chamada, qual foi
a entrada e saida, quanto tempo demorou, quantos tokens foram usados.

### Configuracao

```env
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=docagent
LANGSMITH_TRACING=true
```

A integracao e automatica quando `LANGCHAIN_TRACING_V2=true` esta no ambiente.
Nenhuma mudanca de codigo e necessaria — o LangChain/LangGraph ja instrumenta
automaticamente quando as variaveis estao presentes.

Se `LANGSMITH_API_KEY` nao estiver definida, o tracing e desabilitado
silenciosamente. O agente funciona normalmente.

---

## Streamlit — `src/docagent/ui.py`

Interface de chat simples que consome a API via SSE.

### Comportamento

1. Usuario digita pergunta no input
2. UI gera um `session_id` unico por sessao de browser (armazenado em `st.session_state`)
3. UI faz POST para `/chat` com `question` e `session_id`
4. Recebe o stream SSE e exibe cada chunk em tempo real
5. Historico da conversa e exibido acima do input

### Estado local

```python
st.session_state["session_id"]   # UUID da sessao
st.session_state["messages"]     # historico para exibicao
```

---

## Docker Compose

Apenas FastAPI e Streamlit sao containerizados.
O Ollama fica fora — acessa via `host.docker.internal:11434` no Windows/Mac
ou via rede `host` no Linux.

```yaml
services:
  api:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    environment:
      OLLAMA_BASE_URL: http://host.docker.internal:11434

  ui:
    build: .
    ports: ["8501:8501"]
    environment:
      API_URL: http://api:8000
    depends_on: [api]
```

---

## Estrutura de arquivos

```
docagent/
├── src/docagent/
│   ├── api.py         ← FastAPI + SSE + gerenciamento de sessao
│   └── ui.py          ← Streamlit chat interface
├── Dockerfile
├── docker-compose.yml
└── tests/
    └── test_api.py    ← testes unitarios da API (escritos antes da implementacao)
```

---

## Plano TDD

Os testes sao escritos ANTES da implementacao.
Ordem de desenvolvimento guiada pelos testes:

1. `TestHealthEndpoint` → implementar `GET /health`
2. `TestChatEndpoint` → implementar `POST /chat` com SSE
3. `TestSessionManagement` → implementar criacao, reutilizacao e exclusao de sessao
4. `TestSSEFormat` → garantir formato correto dos eventos
5. `TestLangSmithConfig` → verificar configuracao de tracing

---

## Decisoes de design

| Decisao | Alternativa | Motivo |
|---|---|---|
| SSE em vez de WebSocket | WebSocket | SSE e mais simples para streaming unidirecional (servidor → cliente) e funciona com HTTP padrao |
| Sessoes em memoria | Redis, banco de dados | Suficiente para PoC; Redis seria a escolha em producao |
| Streamlit separado da API | Streamlit com backend integrado | Separacao de responsabilidades; API pode ser consumida por outros clientes |
| Ollama fora do Docker | Ollama em container | GPU no WSL2 com Docker e fragil; nativo e mais estavel |
