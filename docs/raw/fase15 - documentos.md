# Fase 15 — Documentos RAG por Agente

## Objetivo

Vincular documentos PDF ao **agente** em vez do `session_id` do browser, garantindo persistência entre sessões e permitindo gestão (listagem e remoção) de documentos por agente.

Pré-requisito: **Fase 11 concluída** (MCP, ConfigurableAgent com session_collection).

---

## Problema Atual

Documentos são indexados no ChromaDB com `collection_name=session_id` (UUID gerado pelo browser):

```
Upload PDF → ChromaDB collection "abc-123-def-456"
```

Ao fechar o browser, o `session_id` muda → o agente não encontra mais os documentos.

---

## Solução

`collection_name = agente_{agente_id}` — vinculado ao agente, não à sessão.

```
Upload PDF → ChromaDB collection "agente_3"
Conversa → agente busca em "agente_3" (sempre)
```

Além disso, um registro na tabela `Documento` (SQLite) rastreia quais arquivos foram indexados para cada agente, habilitando listagem e remoção.

---

## Modelos de Dados

**`src/docagent/agente/models.py`**

```python
class Documento(Base):
    __tablename__ = "documento"

    agente_id: Mapped[int] = mapped_column(
        ForeignKey("agente.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    agente: Mapped["Agente"] = relationship("Agente", back_populates="documentos")
```

Adicionado em `Agente`:
```python
documentos: Mapped[list["Documento"]] = relationship(
    "Documento", back_populates="agente", cascade="all, delete-orphan"
)
```

**Convenção de collection ChromaDB:**

```
agente_{agente_id}
```

Exemplos: `agente_1`, `agente_3`, `agente_42`.

`collection_name` **não é armazenado** no banco — é sempre derivado de `agente_id`.

---

## Endpoints Backend

**Prefixo: `/api/agentes/{agente_id}/documentos`**

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| GET | `/api/agentes/{id}/documentos` | User | Lista documentos indexados do agente |
| POST | `/api/agentes/{id}/documentos` | User | Upload PDF → ingere no ChromaDB + salva registro |
| DELETE | `/api/agentes/{id}/documentos/{doc_id}` | User | Remove chunks do ChromaDB + registro do banco |

**Validações:**
- Upload de arquivo duplicado (mesmo `filename` no mesmo agente) retorna 409 Conflict
- Agente inexistente retorna 404

---

## Remoção de Documentos do ChromaDB

O ChromaDB não tem `delete(where=...)` direto via `langchain_chroma`. O fluxo é:

```python
# 1. Buscar IDs dos chunks pelo metadata "source_file"
results = vectorstore.get(where={"source_file": filename})
ids = results.get("ids", [])

# 2. Deletar por IDs
if ids:
    vectorstore.delete(ids=ids)
```

Implementado em `delete_document_from_vectorstore(filename, collection_name)` em `src/docagent/ingest.py`.

---

## Mudanças em Arquivos Existentes

| Arquivo | Mudança |
|---------|---------|
| `agente/models.py` | + classe `Documento`, + `relationship` em `Agente` |
| `agente/schemas.py` | + `DocumentoPublic`, `DocumentoUploadResponse` |
| `agente/router.py` | + 3 endpoints de documentos |
| `ingest.py` | + `delete_document_from_vectorstore()` |
| `routers/chat.py` | `session_collection=session_id` → `session_collection=f"agente_{agente.id}"` |

**Novo arquivo:**
- `src/docagent/agente/documento_service.py` — `DocumentoService` (list, create, delete)

### `DocumentoService.create` — detalhe importante

`IngestService.ingest()` é **síncrono** (bloqueia I/O com ChromaDB e Ollama). Em método `async`, deve ser executado via `run_in_executor` para não bloquear o event loop:

```python
loop = asyncio.get_event_loop()
result = await loop.run_in_executor(
    None,
    lambda: IngestService().ingest(filename, content, collection_name),
)
```

---

## Frontend

### `AgenteFormView.vue` — card "Documentos"

Adicionado no modo edição (`/agentes/:id/editar`) como terceiro card na coluna da esquerda:

- Lista dos documentos indexados (filename, chunks)
- Botão "Remover" por documento (confirmação implícita pelo loading)
- Input de upload de PDF com feedback "Indexando..."
- Erro 409 (duplicata) exibido ao usuário

### `client.ts` — novos tipos e endpoints

```typescript
interface Documento {
  id: number
  agente_id: number
  filename: string
  chunks: number
  created_at: string
  updated_at: string
  collection_id?: string
}

api.listDocumentos(agenteId)               // GET /agentes/{id}/documentos
api.uploadDocumento(agenteId, file)        // POST /agentes/{id}/documentos
api.removerDocumento(agenteId, docId)      // DELETE /agentes/{id}/documentos/{docId}
```

---

## Testes (TDD)

```
tests/test_documentos/
├── __init__.py
├── conftest.py                    # fixtures: db_session, client, auth_headers, mock_ingest, mock_chroma_delete
├── test_documento_service.py      # ~17 testes unitários do DocumentoService
└── test_documento_router.py       # ~14 testes de integração dos endpoints
```

### `test_documento_service.py`

```python
class TestListarDocumentos:
    test_retorna_lista_vazia_sem_documentos
    test_retorna_documentos_do_agente
    test_nao_retorna_docs_de_outro_agente

class TestCriarDocumento:
    test_persiste_no_banco
    test_retorna_objeto_documento
    test_persiste_filename_correto
    test_persiste_chunks_correto
    test_chama_ingest_com_collection_agente_id   # "agente_{id}"
    test_rejeita_filename_duplicado_mesmo_agente  # ValueError
    test_permite_mesmo_filename_em_agente_diferente

class TestDeletarDocumento:
    test_retorna_true_ao_deletar
    test_remove_do_banco
    test_chama_delete_document_from_vectorstore
    test_passa_filename_correto_para_chroma
    test_passa_collection_name_correto_para_chroma
    test_retorna_false_para_id_inexistente
    test_nao_chama_chroma_se_doc_nao_existe
```

### `test_documento_router.py`

```python
class TestListarDocumentos:
    test_sem_auth_retorna_401
    test_agente_inexistente_retorna_404
    test_retorna_lista_vazia
    test_retorna_documentos_apos_upload
    test_resposta_tem_campos_obrigatorios

class TestUploadDocumento:
    test_sem_auth_retorna_401
    test_agente_inexistente_retorna_404
    test_upload_retorna_201
    test_resposta_tem_collection_id_com_prefixo_agente
    test_resposta_tem_filename
    test_resposta_tem_chunks
    test_sem_arquivo_retorna_422
    test_duplicado_retorna_409
    test_doc_aparece_na_listagem_apos_upload

class TestRemoverDocumento:
    test_sem_auth_retorna_401
    test_doc_inexistente_retorna_404
    test_delete_retorna_204
    test_doc_removido_nao_aparece_na_listagem
```

---

## Ordem de Implementação

1. `agente/models.py` — modelo `Documento` + `relationship` em `Agente`
2. `ingest.py` — `delete_document_from_vectorstore()`
3. `agente/schemas.py` — `DocumentoPublic`, `DocumentoUploadResponse`
4. 🔴 **RED** — `tests/test_documentos/conftest.py` + `test_documento_service.py`
5. 🟢 **GREEN** — `agente/documento_service.py`
6. 🔴 **RED** — `tests/test_documentos/test_documento_router.py`
7. 🟢 **GREEN** — endpoints em `agente/router.py`
8. ♻️ **REFACTOR** — `routers/chat.py` (1 linha)
9. 🖥️ **Frontend** — `client.ts` + `AgenteFormView.vue`

---

## Verificação End-to-End

```bash
# Testes
uv run pytest tests/test_documentos/ -v

# Verificar ChromaDB após upload
docker compose exec api uv run python -c "
import chromadb, os
client = chromadb.PersistentClient(path='./data/chroma_db')
for c in client.list_collections():
    print(f'{c.name}: {c.count()} chunks')
"
# Deve mostrar: agente_1: N chunks
```
