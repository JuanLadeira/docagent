"""
Testes TDD para IngestService (services/ingest_service.py).

IngestService encapsula o pipeline de ingestao de PDFs recebidos
como bytes via upload HTTP. Testado com mocks do pipeline existente.
"""
import pytest
from unittest.mock import MagicMock, patch


def make_mock_docs(n=3):
    return [MagicMock() for _ in range(n)]


class TestIngestServiceIngest:
    def _call_ingest(self, filename="test.pdf", content=b"fake pdf", session_id="s-1", n_chunks=3):
        from docagent.rag.ingest_service import IngestService

        with (
            patch("docagent.rag.ingest_service.load_pdfs") as mock_load,
            patch("docagent.rag.ingest_service.split_documents") as mock_split,
            patch("docagent.rag.ingest_service.build_vectorstore") as mock_vs,
        ):
            mock_load.return_value = make_mock_docs(1)
            mock_split.return_value = make_mock_docs(n_chunks)

            service = IngestService()
            result = service.ingest(filename, content, session_id)

        return result, mock_load, mock_split, mock_vs

    def test_returns_filename(self):
        result, *_ = self._call_ingest(filename="documento.pdf")
        assert result["filename"] == "documento.pdf"

    def test_returns_chunk_count(self):
        result, *_ = self._call_ingest(n_chunks=5)
        assert result["chunks"] == 5

    def test_returns_collection_id_as_session_id(self):
        result, *_ = self._call_ingest(session_id="minha-sessao")
        assert result["collection_id"] == "minha-sessao"

    def test_calls_build_vectorstore_with_session_collection(self):
        """Vectorstore deve ser criado com a collection da sessao."""
        _, _, _, mock_vs = self._call_ingest(session_id="sessao-xyz")
        call_kwargs = mock_vs.call_args[1] if mock_vs.call_args[1] else {}
        call_args = mock_vs.call_args[0]
        # collection deve ser passada como arg ou kwarg
        all_args = str(call_args) + str(call_kwargs)
        assert "sessao-xyz" in all_args

    def test_calls_load_pdfs(self):
        """Deve chamar load_pdfs para carregar o arquivo salvo."""
        _, mock_load, *_ = self._call_ingest()
        mock_load.assert_called_once()

    def test_calls_split_documents(self):
        """Deve chamar split_documents apos carregar os docs."""
        _, _, mock_split, _ = self._call_ingest()
        mock_split.assert_called_once()

    def test_split_receives_loaded_docs(self):
        """split_documents deve receber o resultado de load_pdfs."""
        from docagent.rag.ingest_service import IngestService

        loaded_docs = make_mock_docs(2)

        with (
            patch("docagent.rag.ingest_service.load_pdfs", return_value=loaded_docs),
            patch("docagent.rag.ingest_service.split_documents") as mock_split,
            patch("docagent.rag.ingest_service.build_vectorstore"),
        ):
            mock_split.return_value = make_mock_docs(4)
            IngestService().ingest("f.pdf", b"content", "s")

        mock_split.assert_called_once_with(loaded_docs)

    def test_zero_chunks_when_no_docs(self):
        """Se split nao retornar chunks, resultado deve ter chunks=0."""
        result, *_ = self._call_ingest(n_chunks=0)
        assert result["chunks"] == 0
