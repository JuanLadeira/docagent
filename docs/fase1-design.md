# Fase 1 — Design do RAG Pipeline

## O que é RAG

**RAG (Retrieval-Augmented Generation)** é uma técnica que combina busca semântica em documentos com geração de texto por LLMs. Em vez de depender apenas do conhecimento pré-treinado do modelo, o RAG recupera trechos relevantes de uma base de dados vetorial antes de gerar a resposta.

Isso resolve dois problemas fundamentais dos LLMs:
- **Alucinação** — o modelo inventa fatos que não sabe
- **Conhecimento desatualizado** — o modelo não conhece documentos privados ou recentes

---

## O Pipeline completo

```
                        INGESTÃO (uma vez)
                        ──────────────────
PDFs  →  PyMuPDFLoader  →  chunks  →  OllamaEmbeddings  →  ChromaDB
                                       (nomic-embed-text)    (disco)


                        CONSULTA (a cada pergunta)
                        ──────────────────────────
pergunta  →  OllamaEmbeddings  →  busca semântica no ChromaDB
                                            │
                                    top-k chunks + metadados
                                            │
                                     prompt montado
                                            │
                                    ChatOllama (qwen2.5:7b)
                                            │
                                   resposta + citações
```

---

## Ingestão — `ingest.py`

### 1. Carregamento — `load_pdfs()`

```python
PyMuPDFLoader(str(pdf_file)).load()
```

`PyMuPDFLoader` extrai o texto de cada página do PDF preservando metadados como número de página (`page`, índice 0-based) e caminho do arquivo. Cada página vira um `Document` do LangChain.

Um metadado adicional é injetado manualmente:
```python
doc.metadata["source_file"] = pdf_file.name
```
Isso garante que o nome do arquivo apareça nas citações independente do caminho absoluto.

### 2. Divisão em chunks — `split_documents()`

```python
RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ".", " "],
)
```

**Por que dividir?** LLMs têm limite de contexto. Enviar documentos inteiros seria inviável. Chunks menores também geram embeddings mais precisos semanticamente.

**Por que chunk_size=1000?** Equilibrio entre contexto suficiente para responder e precisão do embedding. Chunks muito grandes perdem especificidade; muito pequenos perdem contexto.

**Por que overlap=200?** Garante que frases na borda entre dois chunks não sejam perdidas. Uma informação que começa no final do chunk N estará também no início do chunk N+1.

**Por que esses separators?** O splitter tenta quebrar na ordem: parágrafo → linha → frase → palavra. Respeita a estrutura natural do texto.

### 3. Embeddings e persistência — `build_vectorstore()`

```python
OllamaEmbeddings(model="nomic-embed-text")
Chroma.from_documents(chunks, embeddings, persist_directory=CHROMA_PATH)
```

Cada chunk é convertido em um vetor de 768 dimensões pelo `nomic-embed-text`. Textos com significado similar ficam próximos nesse espaço vetorial.

O ChromaDB persiste os vetores em disco. Isso significa que a ingestão só precisa rodar **uma vez por documento** — consultas subsequentes reconectam ao banco existente.

---

## Consulta — `retriever.py`

### 1. Reconexão ao vectorstore — `load_vectorstore()`

```python
Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)
```

Reconecta ao banco já populado. Os embeddings dos chunks **não são regerados** — apenas os da pergunta são calculados em tempo real para fazer a busca.

### 2. A chain LCEL — `build_chain()`

```python
chain = (
    {
        "context": retriever | format_docs_with_citations,
        "question": RunnablePassthrough(),
    }
    | prompt
    | llm
    | StrOutputParser()
)
```

**LCEL (LangChain Expression Language)** é a forma moderna de compor pipelines no LangChain. Cada `|` passa a saída de um passo como entrada do próximo — similar a pipes Unix.

Passo a passo da chain:
1. `retriever` recebe a pergunta e retorna os 4 chunks mais similares (busca semântica por distância coseno)
2. `format_docs_with_citations` formata os chunks injetando metadados de fonte e página
3. `RunnablePassthrough()` deixa a pergunta original passar sem alteração
4. `prompt` monta o template com `{context}` e `{question}` preenchidos
5. `llm` gera a resposta com `temperature=0` (determinístico para QA factual)
6. `StrOutputParser()` extrai o texto da resposta

### 3. Busca semântica

```python
retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 4},
)
```

**k=4** significa que os 4 chunks com maior similaridade coseno à pergunta são recuperados. Esse valor equilibra contexto suficiente e custo de tokens no prompt.

### 4. Citações de fonte — `format_docs_with_citations()`

```python
page = meta.get("page", 0)
f"[Fonte: {source_file}, p.{page + 1}]\n{doc.page_content}"
```

O metadado `page` do PyMuPDF é 0-indexed. Somamos 1 para exibição humana. As fontes são deduplicadas antes de exibir — um chunk por página, sem repetição.

---

## Estrutura de arquivos

```
src/docagent/
├── ingest.py     ← pipeline de ingestão (roda uma vez por PDF novo)
└── retriever.py  ← busca RAG + QA com citações (roda a cada pergunta)

data/
├── pdfs/         ← PDFs para ingestão (ignorado pelo git)
└── chroma_db/    ← banco vetorial persistido (ignorado pelo git)

tests/
├── test_ingest.py     ← 10 testes unitários com mocks
└── test_retriever.py  ← 12 testes unitários com mocks
```

---

## Decisões de design e trade-offs

| Decisão | Alternativa descartada | Motivo |
|---|---|---|
| `nomic-embed-text` local | OpenAI `text-embedding-3-small` | Sem custo, sem API key, roda na GPU |
| ChromaDB embedded | ChromaDB como servidor, Pinecone | Mais simples para PoC local, zero infra |
| `chunk_size=1000` | 512 ou 2000 | Equilibrio entre precisão e contexto |
| `temperature=0` | 0.7 (padrão) | QA factual exige determinismo |
| `k=4` | k=2 ou k=10 | Cobre casos de resposta multi-página sem estourar contexto |
| LCEL chain | `RetrievalQA` legado | LCEL é a API atual do LangChain, mais composível |

---

## Como usar

```bash
# 1. Coloque PDFs em data/pdfs/

# 2. Ingestão (uma vez por PDF novo)
uv run python -m docagent.ingest

# 3. QA interativo
uv run python -m docagent.retriever

# 4. Testes
uv run pytest tests/ -v
```
