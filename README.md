# DocAgent

Agente de pesquisa em documentos PDF com RAG, memória e ferramentas externas.
Projeto de aprendizado construído em 4 fases progressivas — cada fase ensina um conceito fundamental de agentes de IA.

Tudo roda localmente com [Ollama](https://ollama.com). Sem APIs pagas.

---

## Objetivos

- Aprender os fundamentos de agentes de IA na prática
- Implementar um pipeline RAG do zero com LangChain e ChromaDB
- Construir um agente com ferramentas usando LangGraph
- Adicionar memória de conversação sem estourar o context window
- Servir o agente via API com streaming e observabilidade

---

## Fases do projeto

### Fase 1 — RAG Pipeline `[concluida]`
Pipeline de ingestão e busca em documentos PDF.

- Carrega PDFs com `PyMuPDFLoader`
- Divide em chunks com `RecursiveCharacterTextSplitter` (chunk_size=1000, overlap=200)
- Gera embeddings com `nomic-embed-text` via Ollama
- Persiste no `ChromaDB` como vector store
- Responde perguntas com citações de página usando `qwen2.5:7b`

```bash
uv run python -m docagent.ingest     # ingere PDFs
uv run python -m docagent.retriever  # QA interativo com citações
```

### Fase 2 — Agente com Tools `[concluida]`
Agente ReAct com decisão dinâmica de ferramenta.

- RAG convertido em `Tool` do LangChain
- Web search com `DuckDuckGoSearchRun`
- Grafo de estados com `LangGraph` (StateGraph + aresta condicional)
- Loop ReAct: Reason → Act → Observe → Repeat

```bash
uv run python -m docagent.agent  # agente interativo
```

### Fase 3 — Memória `[em desenvolvimento]`
Contexto persistente ao longo da conversa.

- `summarize node` no LangGraph
- Resumo automático do histórico antigo com `qwen2.5:7b`
- Mensagens recentes mantidas na íntegra
- Threshold configurável via `.env`

### Fase 4 — API e Observabilidade `[planejada]`
Empacotamento e rastreabilidade.

- API com `FastAPI` e streaming SSE
- Rastreamento de cada passo com `LangSmith`
- Interface web com `Streamlit`
- `docker-compose.yml` para FastAPI + Streamlit

---

## Stack

| Componente | Tecnologia |
|---|---|
| LLM local | `qwen2.5:7b` via Ollama |
| Embeddings | `nomic-embed-text` via Ollama |
| Orquestração | LangGraph |
| RAG | LangChain + ChromaDB |
| Memória | Summarize node customizado |
| Ferramentas | LangChain Tools + DuckDuckGo |
| Observabilidade | LangSmith |
| API | FastAPI + streaming SSE |
| UI | Streamlit |

---

## Requisitos

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com) com os modelos abaixo instalados:

```bash
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

---

## Instalacao

```bash
git clone https://github.com/JuanLadeira/docagent.git
cd docagent
uv sync
cp .env.example .env  # ajuste as variaveis se necessario
```

## Configuracao

Crie um arquivo `.env` na raiz do projeto:

```env
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=qwen2.5:7b
EMBED_MODEL=nomic-embed-text
CHROMA_PATH=./data/chroma_db
```

## Uso

```bash
# 1. Coloque seus PDFs em data/pdfs/

# 2. Ingira os documentos (uma vez por PDF novo)
uv run python -m docagent.ingest

# 3. Fase 1 — QA direto com citacoes de pagina
uv run python -m docagent.retriever

# 4. Fase 2 — Agente com ferramentas
uv run python -m docagent.agent

# 5. Testes
uv run pytest tests/ -v
```

---

## Estrutura

```
docagent/
├── data/
│   ├── pdfs/          <- PDFs para ingestao (ignorado pelo git)
│   └── chroma_db/     <- banco vetorial persistido (ignorado pelo git)
├── docs/
│   ├── fase1-design.md
│   ├── fase2-design.md
│   └── fase3-design.md
├── src/docagent/
│   ├── ingest.py      <- Fase 1: pipeline de ingestao
│   ├── retriever.py   <- Fase 1: busca RAG + QA
│   ├── tools.py       <- Fase 2: rag_search + web_search
│   ├── agent.py       <- Fase 2: agente ReAct com LangGraph
│   └── memory.py      <- Fase 3: logica de resumo
├── tests/
│   ├── test_ingest.py
│   ├── test_retriever.py
│   ├── test_tools.py
│   └── test_agent.py
└── pyproject.toml
```

---

## Documentacao

Cada fase tem um documento de design detalhado em `docs/`:

- [`fase1-design.md`](docs/fase1-design.md) — RAG pipeline: chunks, embeddings, LCEL chain
- [`fase2-design.md`](docs/fase2-design.md) — Agente ReAct: StateGraph, nos, aresta condicional
- [`fase3-design.md`](docs/fase3-design.md) — Memoria: summarize node, threshold, injecao de contexto
