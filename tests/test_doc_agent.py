"""
Testes TDD para DocAgent (doc_agent.py) — LEGADO.

doc_agent.py foi removido na reorganização arquitetural.
Equivalente moderno: ConfigurableAgent em docagent.agent.configurable.
"""
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.skip(reason="doc_agent.py removido — use ConfigurableAgent")


class TestDocAgentContract:
    def test_is_subclass_of_base_agent(self):
        """DocAgent deve herdar de BaseAgent."""
        from docagent.agent.base import BaseAgent
        from docagent.doc_agent import DocAgent
        assert issubclass(DocAgent, BaseAgent)

    def test_can_be_instantiated(self):
        """DocAgent nao e abstrato — deve poder ser instanciado."""
        with (
            patch("docagent.tools.OllamaEmbeddings"),
            patch("docagent.tools.Chroma"),
            patch("docagent.tools.DuckDuckGoSearchRun"),
        ):
            from docagent.doc_agent import DocAgent
            agent = DocAgent()
        assert agent is not None

    def test_graph_is_none_before_build(self):
        """Antes de build(), _graph deve ser None."""
        with (
            patch("docagent.tools.OllamaEmbeddings"),
            patch("docagent.tools.Chroma"),
            patch("docagent.tools.DuckDuckGoSearchRun"),
        ):
            from docagent.doc_agent import DocAgent
            agent = DocAgent()
        assert agent._graph is None


class TestDocAgentTools:
    def _get_agent(self):
        with (
            patch("docagent.tools.OllamaEmbeddings"),
            patch("docagent.tools.Chroma"),
            patch("docagent.tools.DuckDuckGoSearchRun"),
        ):
            from docagent.doc_agent import DocAgent
            return DocAgent()

    def test_has_exactly_two_tools(self):
        """DocAgent deve ter exatamente duas tools: rag_search e web_search."""
        agent = self._get_agent()
        assert len(agent.tools) == 2

    def test_has_rag_search_tool(self):
        """Uma das tools deve ser rag_search."""
        agent = self._get_agent()
        tool_names = [t.name for t in agent.tools]
        assert "rag_search" in tool_names

    def test_has_web_search_tool(self):
        """Uma das tools deve ser web_search."""
        agent = self._get_agent()
        tool_names = [t.name for t in agent.tools]
        assert "web_search" in tool_names


class TestDocAgentSystemPrompt:
    def _get_agent(self):
        with (
            patch("docagent.tools.OllamaEmbeddings"),
            patch("docagent.tools.Chroma"),
            patch("docagent.tools.DuckDuckGoSearchRun"),
        ):
            from docagent.doc_agent import DocAgent
            return DocAgent()

    def test_system_prompt_is_string(self):
        agent = self._get_agent()
        assert isinstance(agent.system_prompt, str)

    def test_system_prompt_mentions_rag_search(self):
        """Prompt deve mencionar a tool rag_search para o LLM saber usá-la."""
        agent = self._get_agent()
        assert "rag_search" in agent.system_prompt

    def test_system_prompt_mentions_web_search(self):
        """Prompt deve mencionar a tool web_search."""
        agent = self._get_agent()
        assert "web_search" in agent.system_prompt

    def test_system_prompt_instructs_portuguese(self):
        """Prompt deve instruir o modelo a responder em portugues."""
        agent = self._get_agent()
        assert "portugu" in agent.system_prompt.lower()


class TestDocAgentBuild:
    def test_build_returns_self(self):
        """build() deve retornar a propria instancia para encadeamento."""
        with (
            patch("docagent.tools.OllamaEmbeddings"),
            patch("docagent.tools.Chroma"),
            patch("docagent.tools.DuckDuckGoSearchRun"),
            patch("docagent.agent.base._build_graph", return_value=MagicMock()),
        ):
            from docagent.doc_agent import DocAgent
            agent = DocAgent()
            result = agent.build()
        assert result is agent

    def test_build_sets_graph(self):
        """Apos build(), _graph nao deve ser None."""
        with (
            patch("docagent.tools.OllamaEmbeddings"),
            patch("docagent.tools.Chroma"),
            patch("docagent.tools.DuckDuckGoSearchRun"),
            patch("docagent.agent.base._build_graph", return_value=MagicMock()),
        ):
            from docagent.doc_agent import DocAgent
            agent = DocAgent()
            agent.build()
        assert agent._graph is not None
