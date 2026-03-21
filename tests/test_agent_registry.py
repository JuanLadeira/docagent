"""
Testes TDD para o registry de agentes (agents/registry.py).

Valida que o AGENT_REGISTRY tem os agentes esperados e que
cada AgentConfig referencia skills validas.
"""
import pytest


class TestAgentConfig:
    def test_agent_config_has_id(self):
        from docagent.agents.registry import AgentConfig
        config = AgentConfig(
            id="test", name="Test", description="desc", skill_names=[]
        )
        assert config.id == "test"

    def test_agent_config_has_name(self):
        from docagent.agents.registry import AgentConfig
        config = AgentConfig(
            id="test", name="Agente Teste", description="desc", skill_names=[]
        )
        assert config.name == "Agente Teste"

    def test_agent_config_has_description(self):
        from docagent.agents.registry import AgentConfig
        config = AgentConfig(
            id="test", name="Test", description="descricao", skill_names=[]
        )
        assert config.description == "descricao"

    def test_agent_config_has_skill_names(self):
        from docagent.agents.registry import AgentConfig
        config = AgentConfig(
            id="test", name="Test", description="desc",
            skill_names=["rag_search", "web_search"],
        )
        assert config.skill_names == ["rag_search", "web_search"]


class TestAgentRegistry:
    def test_registry_is_dict(self):
        from docagent.agents.registry import AGENT_REGISTRY
        assert isinstance(AGENT_REGISTRY, dict)

    def test_registry_has_doc_analyst(self):
        from docagent.agents.registry import AGENT_REGISTRY
        assert "doc-analyst" in AGENT_REGISTRY

    def test_registry_has_web_researcher(self):
        from docagent.agents.registry import AGENT_REGISTRY
        assert "web-researcher" in AGENT_REGISTRY

    def test_doc_analyst_has_rag_search(self):
        from docagent.agents.registry import AGENT_REGISTRY
        assert "rag_search" in AGENT_REGISTRY["doc-analyst"].skill_names

    def test_doc_analyst_has_web_search(self):
        from docagent.agents.registry import AGENT_REGISTRY
        assert "web_search" in AGENT_REGISTRY["doc-analyst"].skill_names

    def test_web_researcher_has_only_web_search(self):
        from docagent.agents.registry import AGENT_REGISTRY
        assert AGENT_REGISTRY["web-researcher"].skill_names == ["web_search"]

    def test_each_config_id_matches_key(self):
        """O campo id de cada config deve ser igual a chave no registry."""
        from docagent.agents.registry import AGENT_REGISTRY
        for key, config in AGENT_REGISTRY.items():
            assert config.id == key

    def test_all_configs_have_non_empty_name(self):
        from docagent.agents.registry import AGENT_REGISTRY
        for config in AGENT_REGISTRY.values():
            assert len(config.name) > 0

    def test_all_configs_have_non_empty_description(self):
        from docagent.agents.registry import AGENT_REGISTRY
        for config in AGENT_REGISTRY.values():
            assert len(config.description) > 0
