"""
Testes TDD para Skills (skills/).

Valida o contrato de cada skill: nome, label, icone, descricao e as_tool().
"""
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.tools import BaseTool


# ---------------------------------------------------------------------------
# RagSearchSkill
# ---------------------------------------------------------------------------

class TestRagSearchSkill:
    def _make_skill(self, collection="docagent"):
        with (
            patch("docagent.agent.skills.rag_search.OllamaEmbeddings"),
            patch("docagent.agent.skills.rag_search.Chroma"),
        ):
            from docagent.agent.skills.rag_search import RagSearchSkill
            return RagSearchSkill(collection=collection)

    def test_name_is_rag_search(self):
        skill = self._make_skill()
        assert skill.name == "rag_search"

    def test_has_label(self):
        skill = self._make_skill()
        assert isinstance(skill.label, str) and len(skill.label) > 0

    def test_has_icon(self):
        skill = self._make_skill()
        assert isinstance(skill.icon, str) and len(skill.icon) > 0

    def test_has_description(self):
        skill = self._make_skill()
        assert isinstance(skill.description, str) and len(skill.description) > 0

    def test_as_tool_returns_base_tool(self):
        skill = self._make_skill()
        tool = skill.as_tool()
        assert isinstance(tool, BaseTool)

    def test_tool_name_is_rag_search(self):
        skill = self._make_skill()
        assert skill.as_tool().name == "rag_search"

    def test_accepts_custom_collection(self):
        """Skill deve aceitar collection customizada para RAG por sessao."""
        skill = self._make_skill(collection="sessao-xyz")
        assert skill._collection == "sessao-xyz"


# ---------------------------------------------------------------------------
# WebSearchSkill
# ---------------------------------------------------------------------------

class TestWebSearchSkill:
    def _make_skill(self):
        with patch("docagent.agent.skills.web_search.DuckDuckGoSearchRun"):
            from docagent.agent.skills.web_search import WebSearchSkill
            return WebSearchSkill()

    def test_name_is_web_search(self):
        skill = self._make_skill()
        assert skill.name == "web_search"

    def test_has_label(self):
        skill = self._make_skill()
        assert isinstance(skill.label, str) and len(skill.label) > 0

    def test_has_icon(self):
        skill = self._make_skill()
        assert isinstance(skill.icon, str) and len(skill.icon) > 0

    def test_has_description(self):
        skill = self._make_skill()
        assert isinstance(skill.description, str) and len(skill.description) > 0

    def test_as_tool_returns_base_tool(self):
        """as_tool() deve retornar uma instancia de BaseTool."""
        with patch("docagent.agent.skills.web_search.DuckDuckGoSearchRun") as mock_cls:
            mock_tool = MagicMock(spec=BaseTool)
            mock_tool.name = "web_search"
            mock_cls.return_value = mock_tool

            from importlib import reload
            import docagent.agent.skills.web_search as ws_mod
            reload(ws_mod)
            skill = ws_mod.WebSearchSkill()
            tool = skill.as_tool()

        assert isinstance(tool, BaseTool)

    def test_tool_name_is_web_search(self):
        skill = self._make_skill()
        tool = skill.as_tool()
        assert tool.name == "web_search"


# ---------------------------------------------------------------------------
# Skill protocol — duck typing
# ---------------------------------------------------------------------------

class TestSkillProtocol:
    def test_rag_search_satisfies_protocol(self):
        """RagSearchSkill deve ter todos os atributos do protocolo Skill."""
        with (
            patch("docagent.agent.skills.rag_search.OllamaEmbeddings"),
            patch("docagent.agent.skills.rag_search.Chroma"),
        ):
            from docagent.agent.skills.rag_search import RagSearchSkill
            skill = RagSearchSkill()

        assert hasattr(skill, "name")
        assert hasattr(skill, "label")
        assert hasattr(skill, "icon")
        assert hasattr(skill, "description")
        assert callable(skill.as_tool)

    def test_web_search_satisfies_protocol(self):
        """WebSearchSkill deve ter todos os atributos do protocolo Skill."""
        with patch("docagent.agent.skills.web_search.DuckDuckGoSearchRun"):
            from docagent.agent.skills.web_search import WebSearchSkill
            skill = WebSearchSkill()

        assert hasattr(skill, "name")
        assert hasattr(skill, "label")
        assert hasattr(skill, "icon")
        assert hasattr(skill, "description")
        assert callable(skill.as_tool)
