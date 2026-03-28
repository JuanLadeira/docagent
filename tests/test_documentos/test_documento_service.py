"""
Testes unitários do DocumentoService (Fase 15 — TDD).
IngestService e delete_document_from_vectorstore são mockados.
"""
import pytest
import pytest_asyncio
from unittest.mock import patch
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.agente.documento_service import DocumentoService
from docagent.agente.models import Agente, Documento


@pytest_asyncio.fixture
async def service(db_session: AsyncSession) -> DocumentoService:
    return DocumentoService(db_session)


@pytest_asyncio.fixture
async def agente_a(db_session: AsyncSession) -> Agente:
    a = Agente(nome="Agente A", descricao="", skill_names=["rag_search"], ativo=True)
    db_session.add(a)
    await db_session.flush()
    await db_session.refresh(a)
    return a


@pytest_asyncio.fixture
async def agente_b(db_session: AsyncSession) -> Agente:
    b = Agente(nome="Agente B", descricao="", skill_names=["rag_search"], ativo=True)
    db_session.add(b)
    await db_session.flush()
    await db_session.refresh(b)
    return b


async def _criar_doc(service, agente_id, filename="doc.pdf", chunks=5):
    """Helper: cria documento com ingest mockado."""
    with patch("docagent.agente.documento_service.IngestService") as MockClass:
        instance = MockClass.return_value
        instance.ingest.return_value = {
            "filename": filename,
            "chunks": chunks,
            "collection_id": f"agente_{agente_id}",
        }
        return await service.create(agente_id, filename, b"fake pdf content")


class TestListarDocumentos:
    @pytest.mark.asyncio
    async def test_retorna_lista_vazia_sem_documentos(self, service: DocumentoService, agente_a: Agente):
        result = await service.get_by_agente(agente_a.id)
        assert result == []

    @pytest.mark.asyncio
    async def test_retorna_documentos_do_agente(self, service: DocumentoService, agente_a: Agente):
        await _criar_doc(service, agente_a.id, "relatorio.pdf")
        result = await service.get_by_agente(agente_a.id)
        assert len(result) == 1
        assert result[0].filename == "relatorio.pdf"

    @pytest.mark.asyncio
    async def test_nao_retorna_docs_de_outro_agente(
        self, service: DocumentoService, agente_a: Agente, agente_b: Agente
    ):
        await _criar_doc(service, agente_b.id, "doc_b.pdf")
        result = await service.get_by_agente(agente_a.id)
        assert result == []


class TestCriarDocumento:
    @pytest.mark.asyncio
    async def test_persiste_no_banco(self, service: DocumentoService, agente_a: Agente):
        doc = await _criar_doc(service, agente_a.id)
        assert doc.id is not None

    @pytest.mark.asyncio
    async def test_retorna_objeto_documento(self, service: DocumentoService, agente_a: Agente):
        doc = await _criar_doc(service, agente_a.id)
        assert isinstance(doc, Documento)

    @pytest.mark.asyncio
    async def test_persiste_filename_correto(self, service: DocumentoService, agente_a: Agente):
        doc = await _criar_doc(service, agente_a.id, filename="curriculo.pdf")
        assert doc.filename == "curriculo.pdf"

    @pytest.mark.asyncio
    async def test_persiste_chunks_correto(self, service: DocumentoService, agente_a: Agente):
        doc = await _criar_doc(service, agente_a.id, chunks=9)
        assert doc.chunks == 9

    @pytest.mark.asyncio
    async def test_chama_ingest_com_collection_agente_id(
        self, service: DocumentoService, agente_a: Agente
    ):
        with patch("docagent.agente.documento_service.IngestService") as MockClass:
            instance = MockClass.return_value
            instance.ingest.return_value = {
                "filename": "f.pdf",
                "chunks": 3,
                "collection_id": f"agente_{agente_a.id}",
            }
            await service.create(agente_a.id, "f.pdf", b"bytes")

        call_args = instance.ingest.call_args[0]
        collection_name = call_args[2]
        assert collection_name == f"agente_{agente_a.id}"

    @pytest.mark.asyncio
    async def test_rejeita_filename_duplicado_mesmo_agente(
        self, service: DocumentoService, agente_a: Agente
    ):
        await _criar_doc(service, agente_a.id, "dup.pdf")
        with pytest.raises(ValueError, match="já indexado"):
            await _criar_doc(service, agente_a.id, "dup.pdf")

    @pytest.mark.asyncio
    async def test_permite_mesmo_filename_em_agente_diferente(
        self, service: DocumentoService, agente_a: Agente, agente_b: Agente
    ):
        await _criar_doc(service, agente_a.id, "mesmo.pdf")
        doc_b = await _criar_doc(service, agente_b.id, "mesmo.pdf")
        assert doc_b.id is not None


class TestDeletarDocumento:
    @pytest.mark.asyncio
    async def test_retorna_true_ao_deletar(
        self, service: DocumentoService, agente_a: Agente, mock_chroma_delete
    ):
        doc = await _criar_doc(service, agente_a.id)
        result = await service.delete(doc.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_remove_do_banco(
        self, service: DocumentoService, agente_a: Agente, mock_chroma_delete
    ):
        doc = await _criar_doc(service, agente_a.id)
        await service.delete(doc.id)
        lista = await service.get_by_agente(agente_a.id)
        assert lista == []

    @pytest.mark.asyncio
    async def test_chama_delete_document_from_vectorstore(
        self, service: DocumentoService, agente_a: Agente, mock_chroma_delete
    ):
        doc = await _criar_doc(service, agente_a.id, "alvo.pdf")
        await service.delete(doc.id)
        mock_chroma_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_passa_filename_correto_para_chroma(
        self, service: DocumentoService, agente_a: Agente, mock_chroma_delete
    ):
        doc = await _criar_doc(service, agente_a.id, "arquivo.pdf")
        await service.delete(doc.id)
        args = mock_chroma_delete.call_args[0]
        assert args[0] == "arquivo.pdf"

    @pytest.mark.asyncio
    async def test_passa_collection_name_correto_para_chroma(
        self, service: DocumentoService, agente_a: Agente, mock_chroma_delete
    ):
        doc = await _criar_doc(service, agente_a.id)
        await service.delete(doc.id)
        args = mock_chroma_delete.call_args[0]
        assert args[1] == f"agente_{agente_a.id}"

    @pytest.mark.asyncio
    async def test_retorna_false_para_id_inexistente(self, service: DocumentoService):
        result = await service.delete(9999)
        assert result is False

    @pytest.mark.asyncio
    async def test_nao_chama_chroma_se_doc_nao_existe(
        self, service: DocumentoService, mock_chroma_delete
    ):
        await service.delete(9999)
        mock_chroma_delete.assert_not_called()
