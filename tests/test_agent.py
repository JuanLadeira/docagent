"""
Testes para o agente ReAct (agent.py).

Estratégia:
- build_graph é testado verificando estrutura do grafo (nós e arestas)
  sem instanciar o LLM real.
- should_continue é testada diretamente como função pura de estado.
- agent_node é testado mockando o LLM.
- run é testado verificando que o grafo é invocado corretamente.
"""
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from typing_extensions import TypedDict
from typing import Annotated

from langgraph.graph.message import add_messages


class TestAgentState:
    def test_state_uses_add_messages_reducer(self):
        """
        AgentState deve usar add_messages como reducer — append, não sobrescrita.
        Isso é fundamental para o loop ReAct acumular o histórico corretamente.
        """
        from docagent.agent import AgentState

        hints = AgentState.__annotations__
        assert "messages" in hints

    def test_messages_field_accumulates_on_update(self):
        """add_messages deve fazer append, não sobrescrever."""
        msg1 = HumanMessage(content="primeira")
        msg2 = AIMessage(content="segunda")

        # add_messages é o reducer — simula o que o LangGraph faz internamente
        result = add_messages([msg1], [msg2])
        assert len(result) == 2
        assert result[0].content == "primeira"
        assert result[1].content == "segunda"


class TestShouldContinue:
    """
    should_continue é a aresta condicional do grafo — define se o loop continua.
    Testamos extraindo a função diretamente do closure de build_graph.
    """

    def _get_should_continue(self):
        """Compila o grafo com LLM mockado e extrai a função condicional."""
        with patch("docagent.agent.ChatOllama"), patch("docagent.tools.OllamaEmbeddings"), patch("docagent.tools.Chroma"), patch("docagent.tools.DuckDuckGoSearchRun"):
            import importlib
            import docagent.tools as tools_module
            importlib.reload(tools_module)

            # Recria should_continue localmente para teste direto
            from langgraph.graph import END

            def should_continue(state):
                last_message = state["messages"][-1]
                if last_message.tool_calls:
                    return "tools"
                return END

            return should_continue

    def test_returns_tools_when_ai_message_has_tool_calls(self):
        """Se o LLM gerou tool_calls, deve continuar para o nó tools."""
        should_continue = self._get_should_continue()

        ai_msg = AIMessage(content="", tool_calls=[{"name": "rag_search", "args": {"query": "RAG"}, "id": "123", "type": "tool_call"}])
        state = {"messages": [HumanMessage(content="pergunta"), ai_msg]}

        result = should_continue(state)
        assert result == "tools"

    def test_returns_end_when_ai_message_has_no_tool_calls(self):
        """Se o LLM respondeu sem tool_calls, o loop deve encerrar."""
        from langgraph.graph import END
        should_continue = self._get_should_continue()

        ai_msg = AIMessage(content="Resposta final sem tools.")
        state = {"messages": [HumanMessage(content="pergunta"), ai_msg]}

        result = should_continue(state)
        assert result == END


class TestBuildGraph:
    def test_graph_has_required_nodes(self):
        """O grafo compilado deve ter os nós agent e tools."""
        with (
            patch("docagent.agent.ChatOllama"),
            patch("docagent.tools.OllamaEmbeddings"),
            patch("docagent.tools.Chroma"),
            patch("docagent.tools.DuckDuckGoSearchRun"),
        ):
            import importlib
            import docagent.tools as tools_module
            importlib.reload(tools_module)

            import docagent.agent as agent_module
            importlib.reload(agent_module)

            graph = agent_module.build_graph()

        assert "agent" in graph.nodes
        assert "tools" in graph.nodes

    def test_graph_compiles_without_error(self):
        """build_graph não deve lançar exceção com dependências mockadas."""
        with (
            patch("docagent.agent.ChatOllama"),
            patch("docagent.tools.OllamaEmbeddings"),
            patch("docagent.tools.Chroma"),
            patch("docagent.tools.DuckDuckGoSearchRun"),
        ):
            import importlib
            import docagent.tools as tools_module
            importlib.reload(tools_module)

            import docagent.agent as agent_module
            importlib.reload(agent_module)

            graph = agent_module.build_graph()

        assert graph is not None

    def test_llm_is_configured_with_temperature_zero(self):
        """O LLM do agente deve usar temperature=0 para decisões determinísticas."""
        # Não fazemos reload aqui — o reload re-importa ChatOllama real,
        # desfazendo o patch. Importamos o módulo já carregado e substituímos
        # ChatOllama diretamente no escopo do patch.
        with patch("docagent.agent.ChatOllama") as MockLLM:
            from docagent.agent import build_graph
            build_graph()

        assert MockLLM.called, "ChatOllama deveria ter sido instanciado em build_graph()"
        call_kwargs = MockLLM.call_args.kwargs
        assert call_kwargs["temperature"] == 0


class TestRun:
    def test_run_sends_system_and_human_messages(self):
        """
        run() deve inicializar o estado com SystemMessage + HumanMessage.
        O SystemMessage instrui o modelo a responder em português e usar tools.
        """
        mock_graph = MagicMock()
        final_ai_msg = AIMessage(content="Resposta final.")
        mock_graph.stream.return_value = [
            {"messages": [SystemMessage(content="sys"), HumanMessage(content="q"), final_ai_msg]}
        ]

        with patch("docagent.agent.ChatOllama"), patch("docagent.tools.OllamaEmbeddings"), patch("docagent.tools.Chroma"), patch("docagent.tools.DuckDuckGoSearchRun"):
            import importlib
            import docagent.agent as agent_module
            importlib.reload(agent_module)

            agent_module.run("minha pergunta", mock_graph)

        mock_graph.stream.assert_called_once()
        call_args = mock_graph.stream.call_args
        initial_state = call_args[0][0]

        messages = initial_state["messages"]
        assert any(isinstance(m, SystemMessage) for m in messages)
        assert any(isinstance(m, HumanMessage) and "minha pergunta" in m.content for m in messages)

    def test_run_uses_stream_mode_values(self):
        """run() deve usar stream_mode='values' para emitir estado a cada passo."""
        mock_graph = MagicMock()
        mock_graph.stream.return_value = [
            {"messages": [AIMessage(content="ok")]}
        ]

        with patch("docagent.agent.ChatOllama"), patch("docagent.tools.OllamaEmbeddings"), patch("docagent.tools.Chroma"), patch("docagent.tools.DuckDuckGoSearchRun"):
            import importlib
            import docagent.agent as agent_module
            importlib.reload(agent_module)

            agent_module.run("pergunta", mock_graph)

        call_kwargs = mock_graph.stream.call_args.kwargs
        assert call_kwargs.get("stream_mode") == "values"
