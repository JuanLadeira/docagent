"""
Testes de integração dos endpoints de documentos por agente (Fase 15 — TDD).
IngestService e delete_document_from_vectorstore são mockados via fixtures do conftest.
"""
import pytest
from httpx import AsyncClient

FAKE_PDF = b"%PDF-1.4 fake content for testing"


async def _create_agente(client: AsyncClient, headers: dict) -> dict:
    r = await client.post(
        "/api/agentes/",
        json={"nome": "Agente RAG", "descricao": "", "skill_names": ["rag_search"], "ativo": True},
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()


async def _upload_doc(
    client: AsyncClient,
    agente_id: int,
    headers: dict,
    filename: str = "doc.pdf",
) -> dict:
    r = await client.post(
        f"/api/agentes/{agente_id}/documentos",
        files={"file": (filename, FAKE_PDF, "application/pdf")},
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()


class TestListarDocumentos:
    @pytest.mark.asyncio
    async def test_sem_auth_retorna_401(self, client: AsyncClient, auth_headers: dict, mock_ingest):
        agente = await _create_agente(client, auth_headers)
        r = await client.get(f"/api/agentes/{agente['id']}/documentos")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_agente_inexistente_retorna_404(self, client: AsyncClient, auth_headers: dict):
        r = await client.get("/api/agentes/9999/documentos", headers=auth_headers)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_retorna_lista_vazia(self, client: AsyncClient, auth_headers: dict):
        agente = await _create_agente(client, auth_headers)
        r = await client.get(f"/api/agentes/{agente['id']}/documentos", headers=auth_headers)
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_retorna_documentos_apos_upload(
        self, client: AsyncClient, auth_headers: dict, mock_ingest
    ):
        agente = await _create_agente(client, auth_headers)
        await _upload_doc(client, agente["id"], auth_headers)
        r = await client.get(f"/api/agentes/{agente['id']}/documentos", headers=auth_headers)
        assert r.status_code == 200
        assert len(r.json()) == 1

    @pytest.mark.asyncio
    async def test_resposta_tem_campos_obrigatorios(
        self, client: AsyncClient, auth_headers: dict, mock_ingest
    ):
        agente = await _create_agente(client, auth_headers)
        await _upload_doc(client, agente["id"], auth_headers, "curriculo.pdf")
        r = await client.get(f"/api/agentes/{agente['id']}/documentos", headers=auth_headers)
        doc = r.json()[0]
        assert "id" in doc
        assert "agente_id" in doc
        assert "filename" in doc
        assert "chunks" in doc
        assert "created_at" in doc


class TestUploadDocumento:
    @pytest.mark.asyncio
    async def test_sem_auth_retorna_401(self, client: AsyncClient, auth_headers: dict):
        agente = await _create_agente(client, auth_headers)
        r = await client.post(
            f"/api/agentes/{agente['id']}/documentos",
            files={"file": ("doc.pdf", FAKE_PDF, "application/pdf")},
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_agente_inexistente_retorna_404(
        self, client: AsyncClient, auth_headers: dict, mock_ingest
    ):
        r = await client.post(
            "/api/agentes/9999/documentos",
            files={"file": ("doc.pdf", FAKE_PDF, "application/pdf")},
            headers=auth_headers,
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_retorna_201(
        self, client: AsyncClient, auth_headers: dict, mock_ingest
    ):
        agente = await _create_agente(client, auth_headers)
        r = await client.post(
            f"/api/agentes/{agente['id']}/documentos",
            files={"file": ("doc.pdf", FAKE_PDF, "application/pdf")},
            headers=auth_headers,
        )
        assert r.status_code == 201

    @pytest.mark.asyncio
    async def test_resposta_tem_id(self, client: AsyncClient, auth_headers: dict, mock_ingest):
        agente = await _create_agente(client, auth_headers)
        doc = await _upload_doc(client, agente["id"], auth_headers)
        assert "id" in doc
        assert isinstance(doc["id"], int)

    @pytest.mark.asyncio
    async def test_resposta_tem_collection_id_com_prefixo_agente(
        self, client: AsyncClient, auth_headers: dict, mock_ingest
    ):
        agente = await _create_agente(client, auth_headers)
        doc = await _upload_doc(client, agente["id"], auth_headers)
        assert doc["collection_id"] == f"agente_{agente['id']}"

    @pytest.mark.asyncio
    async def test_resposta_tem_filename(
        self, client: AsyncClient, auth_headers: dict, mock_ingest
    ):
        agente = await _create_agente(client, auth_headers)
        doc = await _upload_doc(client, agente["id"], auth_headers, "meu_arquivo.pdf")
        assert doc["filename"] == "meu_arquivo.pdf"

    @pytest.mark.asyncio
    async def test_resposta_tem_chunks(
        self, client: AsyncClient, auth_headers: dict, mock_ingest
    ):
        agente = await _create_agente(client, auth_headers)
        mock_ingest.ingest.return_value["chunks"] = 7
        doc = await _upload_doc(client, agente["id"], auth_headers)
        assert doc["chunks"] == 7

    @pytest.mark.asyncio
    async def test_sem_arquivo_retorna_422(
        self, client: AsyncClient, auth_headers: dict
    ):
        agente = await _create_agente(client, auth_headers)
        r = await client.post(
            f"/api/agentes/{agente['id']}/documentos",
            headers=auth_headers,
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_duplicado_retorna_409(
        self, client: AsyncClient, auth_headers: dict, mock_ingest
    ):
        agente = await _create_agente(client, auth_headers)
        await _upload_doc(client, agente["id"], auth_headers, "dup.pdf")
        r = await client.post(
            f"/api/agentes/{agente['id']}/documentos",
            files={"file": ("dup.pdf", FAKE_PDF, "application/pdf")},
            headers=auth_headers,
        )
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_doc_aparece_na_listagem_apos_upload(
        self, client: AsyncClient, auth_headers: dict, mock_ingest
    ):
        agente = await _create_agente(client, auth_headers)
        await _upload_doc(client, agente["id"], auth_headers, "listado.pdf")
        r = await client.get(f"/api/agentes/{agente['id']}/documentos", headers=auth_headers)
        filenames = [d["filename"] for d in r.json()]
        assert "listado.pdf" in filenames


class TestRemoverDocumento:
    @pytest.mark.asyncio
    async def test_sem_auth_retorna_401(
        self, client: AsyncClient, auth_headers: dict, mock_ingest, mock_chroma_delete
    ):
        agente = await _create_agente(client, auth_headers)
        doc = await _upload_doc(client, agente["id"], auth_headers)
        r = await client.delete(f"/api/agentes/{agente['id']}/documentos/{doc['id']}")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_doc_inexistente_retorna_404(
        self, client: AsyncClient, auth_headers: dict
    ):
        agente = await _create_agente(client, auth_headers)
        r = await client.delete(
            f"/api/agentes/{agente['id']}/documentos/9999", headers=auth_headers
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_retorna_204(
        self, client: AsyncClient, auth_headers: dict, mock_ingest, mock_chroma_delete
    ):
        agente = await _create_agente(client, auth_headers)
        doc = await _upload_doc(client, agente["id"], auth_headers)
        r = await client.delete(
            f"/api/agentes/{agente['id']}/documentos/{doc['id']}", headers=auth_headers
        )
        assert r.status_code == 204

    @pytest.mark.asyncio
    async def test_doc_removido_nao_aparece_na_listagem(
        self, client: AsyncClient, auth_headers: dict, mock_ingest, mock_chroma_delete
    ):
        agente = await _create_agente(client, auth_headers)
        doc = await _upload_doc(client, agente["id"], auth_headers, "remover.pdf")
        await client.delete(
            f"/api/agentes/{agente['id']}/documentos/{doc['id']}", headers=auth_headers
        )
        r = await client.get(f"/api/agentes/{agente['id']}/documentos", headers=auth_headers)
        assert r.json() == []
