"""
Testes para o pipeline de busca e QA (retriever.py).

Estratégia:
- format_docs_with_citations é pura — testada diretamente.
- load_vectorstore e build_chain dependem de Ollama/ChromaDB — testadas com mocks.
- ask é testada verificando que as peças (chain.invoke, retriever.invoke) são chamadas.
"""
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document

from docagent.rag.retriever import format_docs_with_citations, load_vectorstore, build_chain, ask


class TestFormatDocsWithCitations:
    """
    Função pura — zero dependências externas.
    Responsável por formatar chunks com metadados de fonte antes de enviar ao LLM.
    """

    def test_formats_single_doc_correctly(self):
        doc = Document(
            page_content="RAG combina busca semântica com LLMs.",
            metadata={"source_file": "guia.pdf", "page": 1},
        )
        result = format_docs_with_citations([doc])
        assert "[Fonte: guia.pdf, p.2]" in result  # page é 0-indexed, exibe +1
        assert "RAG combina busca semântica com LLMs." in result

    def test_multiple_docs_are_separated(self):
        docs = [
            Document(page_content="Chunk A", metadata={"source_file": "a.pdf", "page": 0}),
            Document(page_content="Chunk B", metadata={"source_file": "b.pdf", "page": 2}),
        ]
        result = format_docs_with_citations(docs)
        assert "Chunk A" in result
        assert "Chunk B" in result
        assert "---" in result  # separador entre chunks

    def test_missing_source_file_uses_fallback(self):
        """Metadado ausente não deve lançar exceção — usa 'desconhecido'."""
        doc = Document(page_content="conteudo", metadata={})
        result = format_docs_with_citations([doc])
        assert "desconhecido" in result

    def test_page_zero_displays_as_one(self):
        """page=0 (índice PyMuPDF) deve ser exibido como p.1 para o usuário."""
        doc = Document(page_content="x", metadata={"source_file": "f.pdf", "page": 0})
        result = format_docs_with_citations([doc])
        assert "p.1" in result

    def test_empty_list_returns_empty_string(self):
        result = format_docs_with_citations([])
        assert result == ""


class TestLoadVectorstore:
    def test_connects_with_correct_collection_name(self, monkeypatch, tmp_path):
        """load_vectorstore deve reconectar à collection 'docagent' no ChromaDB."""
        monkeypatch.setenv("CHROMA_PATH", str(tmp_path))
        monkeypatch.setenv("EMBED_MODEL", "nomic-embed-text")

        with (
            patch("docagent.rag.retriever.OllamaEmbeddings"),
            patch("docagent.rag.retriever.Chroma") as MockChroma,
        ):
            load_vectorstore()

        call_kwargs = MockChroma.call_args.kwargs
        assert call_kwargs["collection_name"] == "docagent"

    def test_uses_env_vars_for_configuration(self, monkeypatch, tmp_path):
        """Modelo e URL do Ollama devem vir das variáveis de ambiente."""
        monkeypatch.setenv("EMBED_MODEL", "meu-modelo-embed")
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://meu-ollama:11434")
        monkeypatch.setenv("CHROMA_PATH", str(tmp_path))

        with (
            patch("docagent.rag.retriever.OllamaEmbeddings") as MockEmbed,
            patch("docagent.rag.retriever.Chroma"),
        ):
            load_vectorstore()

        call_kwargs = MockEmbed.call_args.kwargs
        assert call_kwargs["model"] == "meu-modelo-embed"
        assert call_kwargs["base_url"] == "http://meu-ollama:11434"


class TestBuildChain:
    def test_returns_chain_and_retriever(self, monkeypatch):
        """build_chain deve retornar a chain LCEL e o retriever."""
        monkeypatch.setenv("LLM_MODEL", "qwen2.5:7b")

        mock_vs = MagicMock()
        mock_retriever = MagicMock()
        mock_vs.as_retriever.return_value = mock_retriever

        with patch("docagent.rag.retriever.ChatOllama"):
            chain, retriever = build_chain(mock_vs)

        assert chain is not None
        assert retriever is mock_retriever

    def test_retriever_uses_similarity_search_with_k4(self, monkeypatch):
        """O retriever deve usar busca por similaridade com k=4."""
        monkeypatch.setenv("LLM_MODEL", "qwen2.5:7b")

        mock_vs = MagicMock()

        with patch("docagent.rag.retriever.ChatOllama"):
            build_chain(mock_vs)

        mock_vs.as_retriever.assert_called_once_with(
            search_type="similarity",
            search_kwargs={"k": 4},
        )

    def test_llm_uses_temperature_zero(self, monkeypatch):
        """LLM deve ter temperature=0 para respostas determinísticas em QA."""
        monkeypatch.setenv("LLM_MODEL", "qwen2.5:7b")
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

        mock_vs = MagicMock()

        with patch("docagent.rag.retriever.ChatOllama") as MockLLM:
            build_chain(mock_vs)

        call_kwargs = MockLLM.call_args.kwargs
        assert call_kwargs["temperature"] == 0


class TestAsk:
    def test_invokes_chain_and_retriever_with_question(self, capsys):
        """ask() deve chamar chain.invoke e retriever.invoke com a pergunta."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = "Resposta de teste."

        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = [
            Document(page_content="chunk", metadata={"source_file": "doc.pdf", "page": 0})
        ]

        ask("O que é RAG?", mock_chain, mock_retriever)

        mock_chain.invoke.assert_called_once_with("O que é RAG?")
        mock_retriever.invoke.assert_called_once_with("O que é RAG?")

    def test_deduplicates_sources(self, capsys):
        """Fontes duplicadas (mesmo arquivo e página) não devem aparecer duas vezes."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = "Resposta."

        # Dois chunks da mesma página
        same_source = {"source_file": "doc.pdf", "page": 0}
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = [
            Document(page_content="chunk 1", metadata=same_source),
            Document(page_content="chunk 2", metadata=same_source),
        ]

        ask("Pergunta qualquer", mock_chain, mock_retriever)

        captured = capsys.readouterr()
        # "página 1" deve aparecer apenas uma vez na saída
        assert captured.out.count("página 1") == 1
