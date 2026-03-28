"""
Testes para o parâmetro extra_tools do ConfigurableAgent (fase 11).

Valida que tools MCP externas são corretamente mescladas com as skills nativas.
"""
from unittest.mock import MagicMock, patch


def make_mock_skill(name="mock_skill"):
    skill = MagicMock()
    skill.name = name
    skill.label = name
    skill.icon = "🔧"
    skill.description = f"Faz {name}"
    mock_tool = MagicMock()
    mock_tool.name = name
    skill.as_tool.return_value = mock_tool
    return skill


def make_mock_mcp_tool(name="mcp_tool"):
    tool = MagicMock()
    tool.name = name
    return tool


class TestExtraToolsMerge:
    def _make_agent(self, skill_names=None, extra_tools=None, registry=None):
        from docagent.agent.registry import AgentConfig
        from docagent.agent.configurable import ConfigurableAgent

        config = AgentConfig(
            id="test", name="Test", description="desc",
            skill_names=skill_names or [],
        )
        reg = registry or {}

        with patch("docagent.agent.configurable.SKILL_REGISTRY", reg):
            return ConfigurableAgent(config, extra_tools=extra_tools)

    def test_extra_tools_none_means_empty(self):
        agent = self._make_agent(extra_tools=None)
        assert agent._extra_tools == []

    def test_extra_tools_default_is_empty(self):
        agent = self._make_agent()
        assert agent._extra_tools == []

    def test_extra_tools_are_included_in_tools(self):
        mcp_tool = make_mock_mcp_tool("read_file")
        agent = self._make_agent(extra_tools=[mcp_tool])
        assert mcp_tool in agent.tools

    def test_extra_tools_added_after_builtin_skills(self):
        """extra_tools aparecem depois das skills nativas na lista tools."""
        skill = make_mock_skill("web_search")
        registry = {"web_search": skill}
        mcp_tool = make_mock_mcp_tool("read_file")

        agent = self._make_agent(
            skill_names=["web_search"],
            extra_tools=[mcp_tool],
            registry=registry,
        )
        tools = agent.tools
        names = [t.name for t in tools]
        assert names.index("web_search") < names.index("read_file")

    def test_total_tools_count_is_sum_of_builtin_and_extra(self):
        skill = make_mock_skill("web_search")
        registry = {"web_search": skill}
        mcp_tool_a = make_mock_mcp_tool("read_file")
        mcp_tool_b = make_mock_mcp_tool("write_file")

        agent = self._make_agent(
            skill_names=["web_search"],
            extra_tools=[mcp_tool_a, mcp_tool_b],
            registry=registry,
        )
        assert len(agent.tools) == 3

    def test_agent_with_only_extra_tools_no_builtin(self):
        mcp_tool = make_mock_mcp_tool("list_dir")
        agent = self._make_agent(extra_tools=[mcp_tool])
        assert len(agent.tools) == 1
        assert agent.tools[0].name == "list_dir"

    def test_extra_tools_list_is_not_mutated(self):
        """A lista passada não deve ser modificada pelo agente."""
        mcp_tool = make_mock_mcp_tool("read_file")
        original = [mcp_tool]
        agent = self._make_agent(extra_tools=original)
        _ = agent.tools
        assert len(original) == 1


class TestMcpSkillNamesIgnoredInBuiltin:
    def test_mcp_skill_names_not_in_registry_are_ignored(self):
        """skill_names com prefixo mcp: não estão no SKILL_REGISTRY e devem ser ignoradas."""
        from docagent.agent.registry import AgentConfig
        from docagent.agent.configurable import ConfigurableAgent

        config = AgentConfig(
            id="test", name="Test", description="desc",
            skill_names=["mcp:1:read_file"],
        )
        # SKILL_REGISTRY não tem entries mcp: — devem ser silenciosamente ignorados
        with patch("docagent.agent.configurable.SKILL_REGISTRY", {}):
            agent = ConfigurableAgent(config, extra_tools=[])

        # Sem extra_tools passadas, tools deve ser lista vazia
        assert agent.tools == []
