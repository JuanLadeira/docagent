"""
Testes para tools.py — LEGADO. tools.py foi removido; use agent/skills/.

Estratégia:
- rag_search e web_search dependem de ChromaDB e DuckDuckGo —
  testadas com mocks para isolar a lógica da tool em si.
- Verificamos que as tools têm nome e descrição corretos,
  pois o LLM usa esses campos para decidir qual tool chamar.
"""
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document

pytestmark = pytest.mark.skip(reason="tools.py removido — use docagent.agent.skills")


class TestRagSearchTool:
    def test_tool_name_and_description_exist(self):
        """
        O nome e a descrição são críticos — o LLM os usa para decidir
        quando chamar esta tool. Se estiverem errados, o agente escolhe mal.
        """
        with (
            patch("docagent.tools.OllamaEmbeddings"),
            patch("docagent.tools.Chroma"),
            patch("docagent.tools.DuckDuckGoSearchRun"),
        ):
            from docagent.tools import rag_search

        assert rag_search.name == "rag_search"
        assert "documento" in rag_search.description.lower() or "pdf" in rag_search.description.lower()

    def test_returns_formatted_results_with_source_and_page(self):
        """rag_search deve retornar os chunks formatados com fonte e página."""
        mock_doc = Document(
            page_content="RAG combina busca semântica com LLMs.",
            metadata={"source_file": "guia.pdf", "page": 1},
        )

        with (
            patch("docagent.tools.OllamaEmbeddings"),
            patch("docagent.tools.Chroma"),
            patch("docagent.tools.DuckDuckGoSearchRun"),
        ):
            import importlib
            import docagent.tools as tools_module
            importlib.reload(tools_module)
            tools_module._retriever = MagicMock()
            tools_module._retriever.invoke.return_value = [mock_doc]

            result = tools_module.rag_search.invoke({"query": "O que é RAG?"})

        assert "guia.pdf" in result
        assert "p.2" in result  # page=1 (0-indexed) → exibido como p.2
        assert "RAG combina busca semântica com LLMs." in result

    def test_returns_message_when_no_docs_found(self):
        """Quando o retriever não encontra nada, deve retornar mensagem clara."""
        with (
            patch("docagent.tools.OllamaEmbeddings"),
            patch("docagent.tools.Chroma"),
            patch("docagent.tools.DuckDuckGoSearchRun"),
        ):
            import importlib
            import docagent.tools as tools_module
            importlib.reload(tools_module)
            tools_module._retriever = MagicMock()
            tools_module._retriever.invoke.return_value = []

            result = tools_module.rag_search.invoke({"query": "pergunta sem resultado"})

        assert "Nenhum" in result or "não encontrado" in result.lower()

    def test_multiple_chunks_are_separated(self):
        """Múltiplos chunks devem ser separados por '---'."""
        docs = [
            Document(page_content="Chunk A", metadata={"source_file": "a.pdf", "page": 0}),
            Document(page_content="Chunk B", metadata={"source_file": "a.pdf", "page": 1}),
        ]

        with (
            patch("docagent.tools.OllamaEmbeddings"),
            patch("docagent.tools.Chroma"),
            patch("docagent.tools.DuckDuckGoSearchRun"),
        ):
            import importlib
            import docagent.tools as tools_module
            importlib.reload(tools_module)
            tools_module._retriever = MagicMock()
            tools_module._retriever.invoke.return_value = docs

            result = tools_module.rag_search.invoke({"query": "qualquer"})

        assert "---" in result
        assert "Chunk A" in result
        assert "Chunk B" in result


class TestWebSearchTool:
    def test_tool_name_and_description_exist(self):
        """web_search deve ter nome e descrição indicando busca na internet."""
        with (
            patch("docagent.tools.OllamaEmbeddings"),
            patch("docagent.tools.Chroma"),
            patch("docagent.tools.DuckDuckGoSearchRun"),
        ):
            from docagent.tools import web_search

        assert web_search.name == "web_search"
        assert any(
            word in web_search.description.lower()
            for word in ["internet", "web", "atual", "duckduckgo"]
        )

    def test_delegates_to_duckduckgo(self):
        """web_search deve delegar a chamada ao DuckDuckGoSearchRun."""
        with (
            patch("docagent.tools.OllamaEmbeddings"),
            patch("docagent.tools.Chroma"),
            patch("docagent.tools.DuckDuckGoSearchRun"),
        ):
            import importlib
            import docagent.tools as tools_module
            importlib.reload(tools_module)
            tools_module._web_search = MagicMock()
            tools_module._web_search.invoke.return_value = "Resultado da web"

            result = tools_module.web_search.invoke({"query": "notícias de hoje"})

        tools_module._web_search.invoke.assert_called_once_with("notícias de hoje")
        assert result == "Resultado da web"


class TestToolsList:
    def test_tools_list_contains_both_tools(self):
        """TOOLS deve exportar exatamente rag_search e web_search."""
        with (
            patch("docagent.tools.OllamaEmbeddings"),
            patch("docagent.tools.Chroma"),
            patch("docagent.tools.DuckDuckGoSearchRun"),
        ):
            import importlib
            import docagent.tools as tools_module
            importlib.reload(tools_module)

        tool_names = [t.name for t in tools_module.TOOLS]
        assert "rag_search" in tool_names
        assert "web_search" in tool_names
        assert len(tools_module.TOOLS) == 2
