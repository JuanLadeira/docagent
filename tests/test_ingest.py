"""
Testes para o pipeline de ingestão (ingest.py).

Estratégia:
- Funções puras (split_documents) são testadas diretamente.
- Funções com dependências externas (Ollama, ChromaDB) são testadas com mocks,
  garantindo que a lógica interna está correta sem precisar de serviços rodando.
"""
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document

from docagent.ingest import load_pdfs, split_documents, build_vectorstore


class TestLoadPdfs:
    def test_empty_directory_returns_empty_list(self, tmp_path):
        """Diretório sem PDFs deve retornar lista vazia sem erros."""
        result = load_pdfs(str(tmp_path))
        assert result == []

    def test_nonexistent_directory_returns_empty_list(self, tmp_path):
        """Diretório inexistente não deve lançar exceção."""
        result = load_pdfs(str(tmp_path / "nao_existe"))
        assert result == []

    def test_metadata_source_file_is_injected(self, tmp_path):
        """Cada documento carregado deve ter o campo source_file nos metadados."""
        fake_doc = Document(page_content="conteudo", metadata={"page": 0})

        with patch("docagent.ingest.PyMuPDFLoader") as MockLoader:
            mock_instance = MagicMock()
            mock_instance.load.return_value = [fake_doc]
            MockLoader.return_value = mock_instance

            # Cria um arquivo .pdf fake para o glob encontrar
            pdf_file = tmp_path / "documento.pdf"
            pdf_file.write_bytes(b"fake pdf content")

            result = load_pdfs(str(tmp_path))

        assert len(result) == 1
        assert result[0].metadata["source_file"] == "documento.pdf"

    def test_multiple_pdfs_are_all_loaded(self, tmp_path):
        """Todos os PDFs do diretório devem ser carregados."""
        fake_doc = Document(page_content="pagina", metadata={})

        with patch("docagent.ingest.PyMuPDFLoader") as MockLoader:
            mock_instance = MagicMock()
            mock_instance.load.return_value = [fake_doc]
            MockLoader.return_value = mock_instance

            for name in ["a.pdf", "b.pdf", "c.pdf"]:
                (tmp_path / name).write_bytes(b"fake")

            result = load_pdfs(str(tmp_path))

        assert len(result) == 3


class TestSplitDocuments:
    """
    split_documents é pura (sem I/O externo) — testável diretamente.
    """

    def test_single_short_document_produces_one_chunk(self):
        """Texto menor que chunk_size não deve ser dividido."""
        doc = Document(page_content="Texto curto.", metadata={"page": 0})
        chunks = split_documents([doc])
        assert len(chunks) == 1

    def test_long_document_is_split_into_multiple_chunks(self):
        """Texto maior que chunk_size deve gerar mais de um chunk."""
        long_text = "palavra " * 500  # ~4000 caracteres, chunk_size=1000
        doc = Document(page_content=long_text, metadata={"page": 0})
        chunks = split_documents([doc])
        assert len(chunks) > 1

    def test_metadata_is_preserved_in_chunks(self):
        """Os metadados do documento original devem ser herdados pelos chunks."""
        doc = Document(
            page_content="conteudo relevante",
            metadata={"page": 3, "source_file": "doc.pdf"},
        )
        chunks = split_documents([doc])
        for chunk in chunks:
            assert chunk.metadata["page"] == 3
            assert chunk.metadata["source_file"] == "doc.pdf"

    def test_empty_document_list_returns_empty(self):
        """Lista vazia de documentos não deve lançar exceção."""
        result = split_documents([])
        assert result == []

    def test_chunk_size_respected(self):
        """
        Chunks devem respeitar o chunk_size quando há separadores no texto.

        Nota: RecursiveCharacterTextSplitter é um limite "suave" — só quebra
        onde há separadores (\n\n, \n, ., espaço). Texto sem separadores não
        pode ser dividido, independente do tamanho. Este teste usa texto
        realista com espaços, que é o caso de uso real do projeto.
        """
        # ~100 palavras × ~10 chars = ~1000+ chars com separadores (espaços)
        long_text = " ".join(["palavra longa"] * 200)  # ~2600 chars
        doc = Document(page_content=long_text, metadata={})
        chunks = split_documents([doc])
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.page_content) <= 1200  # chunk_size=1000 + margem do overlap


class TestBuildVectorstore:
    def test_vectorstore_is_created_with_correct_collection(self, tmp_path, monkeypatch):
        """
        Verifica que build_vectorstore chama o Chroma com a collection correta
        e retorna o vectorstore criado.
        """
        monkeypatch.setenv("CHROMA_PATH", str(tmp_path))
        monkeypatch.setenv("EMBED_MODEL", "nomic-embed-text")

        mock_vectorstore = MagicMock()

        with (
            patch("docagent.ingest.OllamaEmbeddings"),
            patch("docagent.ingest.Chroma.from_documents", return_value=mock_vectorstore) as mock_chroma,
        ):
            chunks = [Document(page_content="teste", metadata={})]
            result = build_vectorstore(chunks)

        mock_chroma.assert_called_once()
        call_kwargs = mock_chroma.call_args.kwargs
        assert call_kwargs["collection_name"] == "docagent"
        assert result is mock_vectorstore
