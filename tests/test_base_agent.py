"""
Testes TDD para BaseAgent (base_agent.py).

Escritos antes da implementacao — definem o contrato que toda subclasse deve cumprir.
"""
import json
import pytest
from abc import ABC
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


# ---------------------------------------------------------------------------
# Subclasse concreta minima para testar a classe base
# ---------------------------------------------------------------------------

class MinimalAgent:
    """Implementacao minima usada apenas nos testes de BaseAgent."""
    pass


# ---------------------------------------------------------------------------
# Instanciacao e contrato ABC
# ---------------------------------------------------------------------------

class TestBaseAgentContract:
    def test_cannot_instantiate_base_agent_directly(self):
        """BaseAgent e abstrata — instanciar diretamente deve lancar TypeError."""
        from docagent.agent.base import BaseAgent
        with pytest.raises(TypeError):
            BaseAgent()

    def test_subclass_without_tools_cannot_be_instantiated(self):
        """Subclasse sem tools abstrata nao pode ser instanciada."""
        from docagent.agent.base import BaseAgent

        class IncompleteAgent(BaseAgent):
            @property
            def system_prompt(self):
                return "prompt"
            # tools nao implementado

        with pytest.raises(TypeError):
            IncompleteAgent()

    def test_subclass_without_system_prompt_cannot_be_instantiated(self):
        """Subclasse sem system_prompt abstrato nao pode ser instanciada."""
        from docagent.agent.base import BaseAgent

        class IncompleteAgent(BaseAgent):
            @property
            def tools(self):
                return []
            # system_prompt nao implementado

        with pytest.raises(TypeError):
            IncompleteAgent()

    def test_subclass_implementing_both_can_be_instantiated(self):
        """Subclasse com tools e system_prompt implementados pode ser criada."""
        from docagent.agent.base import BaseAgent

        class CompleteAgent(BaseAgent):
            @property
            def tools(self):
                return []

            @property
            def system_prompt(self):
                return "sou um agente completo"

        agent = CompleteAgent()
        assert agent is not None

    def test_base_agent_is_abstract(self):
        """BaseAgent deve ser subclasse de ABC."""
        from docagent.agent.base import BaseAgent
        assert issubclass(BaseAgent, ABC)


# ---------------------------------------------------------------------------
# build()
# ---------------------------------------------------------------------------

class TestBaseAgentBuild:
    def _make_agent(self):
        from docagent.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            @property
            def tools(self):
                return []

            @property
            def system_prompt(self):
                return "agente de teste"

        return TestAgent()

    def test_build_returns_self(self):
        """build() deve retornar a propria instancia para encadeamento."""
        agent = self._make_agent()

        with patch("docagent.agent.base._build_graph", return_value=MagicMock()):
            result = agent.build()

        assert result is agent

    def test_build_calls_build_graph_with_tools_and_prompt(self):
        """build() deve passar tools e system_prompt para _build_graph."""
        agent = self._make_agent()

        with patch("docagent.agent.base._build_graph") as mock_build:
            mock_build.return_value = MagicMock()
            agent.build()

        mock_build.assert_called_once_with([], "agente de teste")

    def test_graph_is_none_before_build(self):
        """Antes de build(), o grafo interno deve ser None."""
        agent = self._make_agent()
        assert agent._graph is None

    def test_graph_is_set_after_build(self):
        """Apos build(), o grafo deve estar disponivel."""
        agent = self._make_agent()

        with patch("docagent.agent.base._build_graph", return_value=MagicMock()):
            agent.build()

        assert agent._graph is not None


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------

class TestBaseAgentRun:
    def _make_built_agent(self):
        from docagent.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            @property
            def tools(self):
                return []

            @property
            def system_prompt(self):
                return "agente de teste"

        agent = TestAgent()

        mock_graph = MagicMock()
        mock_graph.stream.return_value = iter([
            {
                "messages": [
                    HumanMessage(content="pergunta"),
                    AIMessage(content="resposta do agente"),
                ],
                "summary": "",
            }
        ])
        agent._graph = mock_graph
        return agent, mock_graph

    def test_run_raises_if_not_built(self):
        """run() sem build() deve lancar RuntimeError."""
        from docagent.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            @property
            def tools(self): return []
            @property
            def system_prompt(self): return "prompt"

        agent = TestAgent()
        with pytest.raises(RuntimeError, match="build\\(\\)"):
            agent.run("pergunta")

    def test_run_returns_dict_with_messages(self):
        """run() deve retornar o estado final com campo messages."""
        agent, _ = self._make_built_agent()
        result = agent.run("pergunta")
        assert "messages" in result

    def test_run_calls_graph_stream(self):
        """run() deve invocar graph.stream com o estado de entrada."""
        agent, mock_graph = self._make_built_agent()
        agent.run("pergunta")
        assert mock_graph.stream.called

    def test_run_with_none_state_creates_empty_state(self):
        """run(state=None) deve inicializar estado vazio."""
        agent, mock_graph = self._make_built_agent()
        agent.run("pergunta", state=None)

        call_args = mock_graph.stream.call_args[0][0]
        assert call_args["summary"] == ""

    def test_run_preserves_existing_state_messages(self):
        """run() com estado anterior deve incluir mensagens existentes."""
        agent, mock_graph = self._make_built_agent()
        existing = {
            "messages": [HumanMessage(content="anterior")],
            "summary": "resumo anterior",
        }
        agent.run("nova pergunta", state=existing)

        call_args = mock_graph.stream.call_args[0][0]
        contents = [m.content for m in call_args["messages"]]
        assert "anterior" in contents

    def test_run_injects_system_and_human_messages(self):
        """run() deve adicionar SystemMessage e HumanMessage ao estado."""
        agent, mock_graph = self._make_built_agent()
        agent.run("minha pergunta")

        call_args = mock_graph.stream.call_args[0][0]
        messages = call_args["messages"]
        assert any(isinstance(m, SystemMessage) for m in messages)
        assert any(
            isinstance(m, HumanMessage) and "minha pergunta" in m.content
            for m in messages
        )


# ---------------------------------------------------------------------------
# stream()
# ---------------------------------------------------------------------------

class TestBaseAgentStream:
    def _make_built_agent(self, ai_content="resposta final"):
        from docagent.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            @property
            def tools(self): return []
            @property
            def system_prompt(self): return "prompt"

        agent = TestAgent()
        mock_graph = MagicMock()
        mock_graph.stream.return_value = iter([
            {
                "messages": [AIMessage(content=ai_content)],
                "summary": "",
            }
        ])
        agent._graph = mock_graph
        return agent

    def _parse_events(self, agent, question="teste"):
        events = []
        for raw in agent.stream(question):
            if raw.startswith("data:"):
                payload = raw[len("data:"):].strip()
                try:
                    events.append(json.loads(payload))
                except json.JSONDecodeError:
                    pass
        return events

    def test_stream_raises_if_not_built(self):
        """stream() sem build() deve lancar RuntimeError."""
        from docagent.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            @property
            def tools(self): return []
            @property
            def system_prompt(self): return "prompt"

        agent = TestAgent()
        with pytest.raises(RuntimeError, match="build\\(\\)"):
            list(agent.stream("pergunta"))

    def test_stream_yields_strings(self):
        """stream() deve gerar strings no formato SSE."""
        agent = self._make_built_agent()
        chunks = list(agent.stream("pergunta"))
        assert all(isinstance(c, str) for c in chunks)

    def test_stream_last_event_is_done(self):
        """Ultimo evento do stream deve ser do tipo done."""
        agent = self._make_built_agent()
        events = self._parse_events(agent)
        assert events[-1]["type"] == "done"

    def test_stream_contains_answer_event(self):
        """Stream deve conter evento com a resposta final."""
        agent = self._make_built_agent("resposta importante")
        events = self._parse_events(agent)
        answer_events = [e for e in events if e.get("type") == "answer"]
        assert len(answer_events) == 1
        assert "resposta importante" in answer_events[0]["content"]

    def test_stream_all_events_have_type(self):
        """Todo evento SSE deve ter o campo type."""
        agent = self._make_built_agent()
        events = self._parse_events(agent)
        assert all("type" in e for e in events)
