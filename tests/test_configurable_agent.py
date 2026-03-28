"""
Testes TDD para ConfigurableAgent (agents/configurable_agent.py).

Valida que ConfigurableAgent monta tools dinamicamente a partir
do AgentConfig e gera um system_prompt descrevendo as skills ativas.
"""
import pytest
from unittest.mock import MagicMock, patch


def make_mock_skill(name="mock_skill", label="Mock Skill", icon="🔧"):
    """Skill mockada que satisfaz o protocolo Skill."""
    skill = MagicMock()
    skill.name = name
    skill.label = label
    skill.icon = icon
    skill.description = f"Faz {name}"
    mock_tool = MagicMock()
    mock_tool.name = name
    skill.as_tool.return_value = mock_tool
    return skill


def make_skill_registry(*names):
    return {name: make_mock_skill(name) for name in names}


# ---------------------------------------------------------------------------
# Contrato com BaseAgent
# ---------------------------------------------------------------------------

class TestConfigurableAgentContract:
    def test_is_subclass_of_base_agent(self):
        from docagent.agent.base import BaseAgent
        from docagent.agent.configurable import ConfigurableAgent
        assert issubclass(ConfigurableAgent, BaseAgent)

    def test_can_be_instantiated_with_config(self):
        from docagent.agent.registry import AgentConfig
        from docagent.agent.configurable import ConfigurableAgent

        config = AgentConfig(
            id="test", name="Test", description="desc",
            skill_names=["rag_search"],
        )
        registry = make_skill_registry("rag_search")

        with patch("docagent.agent.configurable.SKILL_REGISTRY", registry):
            agent = ConfigurableAgent(config)

        assert agent is not None

    def test_graph_is_none_before_build(self):
        from docagent.agent.registry import AgentConfig
        from docagent.agent.configurable import ConfigurableAgent

        config = AgentConfig(
            id="test", name="Test", description="desc", skill_names=[],
        )
        with patch("docagent.agent.configurable.SKILL_REGISTRY", {}):
            agent = ConfigurableAgent(config)

        assert agent._graph is None


# ---------------------------------------------------------------------------
# Propriedade tools
# ---------------------------------------------------------------------------

class TestConfigurableAgentTools:
    def _make_agent(self, skill_names, registry=None):
        from docagent.agent.registry import AgentConfig
        from docagent.agent.configurable import ConfigurableAgent

        config = AgentConfig(
            id="test", name="Test", description="desc",
            skill_names=skill_names,
        )
        reg = registry or make_skill_registry(*skill_names)

        with patch("docagent.agent.configurable.SKILL_REGISTRY", reg):
            return ConfigurableAgent(config)

    def test_tools_returns_list(self):
        with patch("docagent.agent.configurable.SKILL_REGISTRY",
                   make_skill_registry("rag_search")):
            agent = self._make_agent(["rag_search"])
        assert isinstance(agent.tools, list)

    def test_doc_analyst_has_two_tools(self):
        """Config doc-analyst com 2 skills deve gerar 2 tools."""
        from docagent.agent.registry import AGENT_REGISTRY
        from docagent.agent.configurable import ConfigurableAgent

        config = AGENT_REGISTRY["doc-analyst"]
        registry = make_skill_registry("rag_search", "web_search")

        with patch("docagent.agent.configurable.SKILL_REGISTRY", registry):
            agent = ConfigurableAgent(config)

        assert len(agent.tools) == 2

    def test_web_researcher_has_one_tool(self):
        """Config web-researcher com 1 skill deve gerar 1 tool."""
        from docagent.agent.registry import AGENT_REGISTRY
        from docagent.agent.configurable import ConfigurableAgent

        config = AGENT_REGISTRY["web-researcher"]
        registry = make_skill_registry("web_search")

        with patch("docagent.agent.configurable.SKILL_REGISTRY", registry):
            agent = ConfigurableAgent(config)

        assert len(agent.tools) == 1

    def test_tools_calls_as_tool_on_each_skill(self):
        """tools deve chamar as_tool() em cada skill do config."""
        from docagent.agent.registry import AgentConfig
        from docagent.agent.configurable import ConfigurableAgent

        skill_a = make_mock_skill("skill_a")
        skill_b = make_mock_skill("skill_b")
        registry = {"skill_a": skill_a, "skill_b": skill_b}

        config = AgentConfig(
            id="test", name="Test", description="desc",
            skill_names=["skill_a", "skill_b"],
        )
        with patch("docagent.agent.configurable.SKILL_REGISTRY", registry):
            agent = ConfigurableAgent(config)
            _ = agent.tools

        skill_a.as_tool.assert_called_once()
        skill_b.as_tool.assert_called_once()

    def test_unknown_skill_is_ignored(self):
        """Skill inexistente no registry deve ser ignorada sem erro."""
        from docagent.agent.registry import AgentConfig
        from docagent.agent.configurable import ConfigurableAgent

        config = AgentConfig(
            id="test", name="Test", description="desc",
            skill_names=["rag_search", "skill_inexistente"],
        )
        registry = make_skill_registry("rag_search")

        with patch("docagent.agent.configurable.SKILL_REGISTRY", registry):
            agent = ConfigurableAgent(config)

        assert len(agent.tools) == 1


# ---------------------------------------------------------------------------
# Propriedade system_prompt
# ---------------------------------------------------------------------------

class TestConfigurableAgentSystemPrompt:
    def _make_agent(self, skill_names):
        from docagent.agent.registry import AgentConfig
        from docagent.agent.configurable import ConfigurableAgent

        config = AgentConfig(
            id="test", name="Test", description="desc",
            skill_names=skill_names,
        )
        registry = make_skill_registry(*skill_names)

        with patch("docagent.agent.configurable.SKILL_REGISTRY", registry):
            return ConfigurableAgent(config)

    def test_system_prompt_is_string(self):
        agent = self._make_agent(["rag_search"])
        assert isinstance(agent.system_prompt, str)

    def test_system_prompt_mentions_skill_names(self):
        """Prompt deve mencionar cada skill para o LLM saber usa-las."""
        agent = self._make_agent(["rag_search", "web_search"])
        assert "rag_search" in agent.system_prompt
        assert "web_search" in agent.system_prompt

    def test_system_prompt_instructs_portuguese(self):
        agent = self._make_agent([])
        assert "portugu" in agent.system_prompt.lower()

    def test_system_prompt_changes_with_different_skills(self):
        """Agentes com skills diferentes devem ter prompts diferentes."""
        agent_a = self._make_agent(["rag_search"])
        agent_b = self._make_agent(["web_search"])
        assert agent_a.system_prompt != agent_b.system_prompt


# ---------------------------------------------------------------------------
# RAG por sessao
# ---------------------------------------------------------------------------

class TestConfigurableAgentSessionCollection:
    def test_accepts_session_collection(self):
        """Deve aceitar collection customizada para RAG da sessao."""
        from docagent.agent.registry import AgentConfig
        from docagent.agent.configurable import ConfigurableAgent

        config = AgentConfig(
            id="test", name="Test", description="desc", skill_names=[],
        )
        with patch("docagent.agent.configurable.SKILL_REGISTRY", {}):
            agent = ConfigurableAgent(config, session_collection="sessao-xyz")

        assert agent._session_collection == "sessao-xyz"

    def test_default_session_collection_is_none(self):
        from docagent.agent.registry import AgentConfig
        from docagent.agent.configurable import ConfigurableAgent

        config = AgentConfig(
            id="test", name="Test", description="desc", skill_names=[],
        )
        with patch("docagent.agent.configurable.SKILL_REGISTRY", {}):
            agent = ConfigurableAgent(config)

        assert agent._session_collection is None
