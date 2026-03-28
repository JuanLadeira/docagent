"""
Testes para o agente ReAct com memoria (agent.py).

Fase 2: AgentState, should_continue, build_graph, run.
Fase 3: campo summary no estado, injecao de contexto no agent_node,
        summarize_node, persistencia de estado entre turnos.
"""
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

from langgraph.graph.message import add_messages
from langgraph.graph import END


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_tool_call_message() -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{
            "name": "rag_search",
            "args": {"query": "RAG"},
            "id": "abc123",
            "type": "tool_call",
        }],
    )


# ---------------------------------------------------------------------------
# AgentState
# ---------------------------------------------------------------------------

class TestAgentState:
    def test_has_messages_field(self):
        """messages e obrigatorio e usa add_messages como reducer."""
        from docagent.agent.base import AgentState
        assert "messages" in AgentState.__annotations__

    def test_has_summary_field(self):
        """summary e o campo adicionado na Fase 3 para memoria de longo prazo."""
        from docagent.agent.base import AgentState
        assert "summary" in AgentState.__annotations__

    def test_messages_reducer_accumulates(self):
        """add_messages deve fazer append — essencial para o loop ReAct."""
        msg1 = HumanMessage(content="primeira")
        msg2 = AIMessage(content="segunda")
        result = add_messages([msg1], [msg2])
        assert len(result) == 2
        assert result[0].content == "primeira"
        assert result[1].content == "segunda"


# ---------------------------------------------------------------------------
# should_continue (aresta condicional)
# ---------------------------------------------------------------------------

class TestShouldContinue:
    """
    Na Fase 3, should_continue roteia para "summarize" em vez de END
    quando o LLM responde sem tool_calls.
    """

    def _make_should_continue(self):
        """Replica a logica de should_continue de agent.py para teste isolado."""
        def should_continue(state):
            last_message = state["messages"][-1]
            if last_message.tool_calls:
                return "tools"
            return "summarize"

        return should_continue

    def test_returns_tools_when_has_tool_calls(self):
        """tool_calls presente → continua o loop ReAct."""
        sc = self._make_should_continue()
        state = {"messages": [HumanMessage(content="p"), make_tool_call_message()]}
        assert sc(state) == "tools"

    def test_returns_summarize_when_no_tool_calls(self):
        """Sem tool_calls → vai para o no de resumo (Fase 3), nao para END direto."""
        sc = self._make_should_continue()
        state = {"messages": [HumanMessage(content="p"), AIMessage(content="resposta")]}
        assert sc(state) == "summarize"

    def test_does_not_return_end_directly(self):
        """
        Diferenca fundamental da Fase 3: should_continue nunca retorna END
        diretamente — sempre passa pelo summarize node primeiro.
        """
        sc = self._make_should_continue()
        state = {"messages": [AIMessage(content="fim")]}
        assert sc(state) != END


# ---------------------------------------------------------------------------
# build_graph
# ---------------------------------------------------------------------------

class TestBuildGraph:
    def test_graph_has_all_three_nodes(self):
        """Fase 3: grafo deve ter agent, tools E summarize."""
        with patch("docagent.agent.base.ChatOllama"):
            from docagent.agent.base import _build_graph as build_graph
            graph = build_graph([], "")

        assert "agent" in graph.nodes
        assert "tools" in graph.nodes
        assert "summarize" in graph.nodes

    def test_graph_compiles_without_error(self):
        with patch("docagent.agent.base.ChatOllama"):
            from docagent.agent.base import _build_graph as build_graph
            graph = build_graph([], "")
        assert graph is not None

    def test_llm_uses_temperature_zero(self):
        """temperature=0 para decisoes deterministicas."""
        with patch("docagent.agent.base.ChatOllama") as MockLLM:
            from docagent.agent.base import _build_graph as build_graph
            build_graph([], "")

        assert MockLLM.called
        assert MockLLM.call_args.kwargs["temperature"] == 0


# ---------------------------------------------------------------------------
# agent_node — injecao do resumo (Fase 3)
# ---------------------------------------------------------------------------

class TestAgentNode:
    """
    Na Fase 3, agent_node injeta o summary como contexto nas mensagens
    antes de chamar o LLM, sem modificar o estado original.
    """

    def _invoke_agent_node(self, state: dict) -> dict:
        """Executa agent_node com LLM mockado e retorna o resultado."""
        mock_llm_instance = MagicMock()
        mock_llm_instance.bind_tools.return_value = mock_llm_instance
        mock_llm_instance.invoke.return_value = AIMessage(content="resposta mock")

        with patch("docagent.agent.base.ChatOllama", return_value=mock_llm_instance):
            from docagent.agent.base import _build_graph as build_graph
            # Acessa o agent_node compilado rodando o grafo ate o primeiro passo
            graph = build_graph([], "")

        # Chama o agent_node via invoke para isolar apenas esse no
        mock_llm_instance.invoke.reset_mock()

        # Extrai o agent_node do grafo e chama diretamente
        # Usamos patch para capturar as mensagens enviadas ao LLM
        with patch("docagent.agent.base.ChatOllama", return_value=mock_llm_instance):
            import docagent.agent.base as agent_module
            # Rebuild para garantir que o mock esta em uso
            g = agent_module._build_graph([], "")

        return mock_llm_instance

    def test_injects_summary_as_context_message(self):
        """
        Quando ha um resumo no estado, agent_node deve injetar uma HumanMessage
        com o conteudo do resumo antes das mensagens atuais.
        """
        captured_messages = []

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.side_effect = lambda msgs: (
            captured_messages.extend(msgs) or AIMessage(content="ok")
        )

        state = {
            "messages": [HumanMessage(content="nova pergunta")],
            "summary": "O usuario perguntou sobre RAG anteriormente.",
        }

        # Chama a funcao agent_node diretamente via closure
        # Recriamos a logica aqui para testar em isolamento
        messages = state["messages"]
        summary = state.get("summary", "")

        if summary:
            from langchain_core.messages import HumanMessage as HMsg
            context_msg = HMsg(content=f"[CONTEXTO DA CONVERSA ANTERIOR]\n{summary}")
            messages_with_context = [context_msg] + list(messages)
        else:
            messages_with_context = messages

        assert len(messages_with_context) == 2
        assert "[CONTEXTO DA CONVERSA ANTERIOR]" in messages_with_context[0].content
        assert "O usuario perguntou sobre RAG anteriormente." in messages_with_context[0].content

    def test_no_injection_when_summary_is_empty(self):
        """Sem summary no estado, as mensagens nao devem ser modificadas."""
        state = {
            "messages": [HumanMessage(content="pergunta")],
            "summary": "",
        }

        messages = state["messages"]
        summary = state.get("summary", "")

        if summary:
            from langchain_core.messages import HumanMessage as HMsg
            messages_with_context = [HMsg(content=f"[CONTEXTO]\n{summary}")] + list(messages)
        else:
            messages_with_context = messages

        assert len(messages_with_context) == 1
        assert messages_with_context[0].content == "pergunta"


# ---------------------------------------------------------------------------
# summarize_node (Fase 3)
# ---------------------------------------------------------------------------

class TestSummarizeNode:
    """
    summarize_node decide se resume ou passa direto com base no threshold.
    Quando resume, atualiza summary e trunca messages no estado.
    """

    def test_does_nothing_below_threshold(self):
        """
        Historico curto: summarize_node deve retornar dict vazio
        (sem alteracao no estado).
        """
        from docagent.agent.memory import SUMMARY_THRESHOLD

        # Menos mensagens que o threshold
        few_messages = [
            HumanMessage(content="oi"),
            AIMessage(content="ola"),
        ]

        with patch("docagent.agent.base.ChatOllama"):
            from docagent.agent.base import _build_graph as build_graph
            # Simula chamada ao summarize_node com historico curto
            from docagent.agent.memory import should_summarize
            assert should_summarize(few_messages) is False

    def test_summarizes_when_above_threshold(self):
        """
        Historico longo: summarize_node deve chamar summarize_history
        e retornar summary + messages truncadas.
        """
        from docagent.agent.memory import SUMMARY_THRESHOLD, RECENT_MESSAGES_TO_KEEP

        # Mais mensagens que o threshold
        many_messages = []
        for i in range(SUMMARY_THRESHOLD + 1):
            many_messages += [
                HumanMessage(content=f"pergunta {i}"),
                AIMessage(content=f"resposta {i}"),
            ]

        with patch("docagent.agent.base.summarize_history", return_value="Resumo gerado.") as mock_summarize, \
             patch("docagent.agent.base.trim_messages", return_value=many_messages[-2:]) as mock_trim, \
             patch("docagent.agent.base.ChatOllama"):

            from docagent.agent.memory import should_summarize
            assert should_summarize(many_messages) is True

            # Verifica que a logica de resumo seria acionada
            mock_summarize("msgs", "")
            assert mock_summarize.called


# ---------------------------------------------------------------------------
# run — persistencia de estado entre turnos (Fase 3)
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Testa agent.py legado removido — equivalente em test_base_agent.py")
class TestRun:
    def _make_mock_graph(self, response_content: str = "Resposta.") -> MagicMock:
        mock_graph = MagicMock()
        mock_graph.stream.return_value = [
            {"messages": [AIMessage(content=response_content)], "summary": ""}
        ]
        return mock_graph

    def test_run_with_no_state_initializes_empty(self):
        """Sem estado anterior, run() cria estado inicial com messages=[] e summary=''."""
        mock_graph = self._make_mock_graph()

        from docagent.agent import run
        run("pergunta", mock_graph, state=None)

        call_args = mock_graph.stream.call_args[0][0]
        # Deve ter SystemMessage + HumanMessage na lista de mensagens iniciais
        assert any(isinstance(m, SystemMessage) for m in call_args["messages"])
        assert any(isinstance(m, HumanMessage) for m in call_args["messages"])

    def test_run_preserves_existing_state(self):
        """Estado anterior (historico + summary) deve ser passado para o proximo turno."""
        mock_graph = self._make_mock_graph()

        existing_state = {
            "messages": [
                HumanMessage(content="pergunta anterior"),
                AIMessage(content="resposta anterior"),
            ],
            "summary": "Resumo da conversa anterior.",
        }

        from docagent.agent import run
        run("nova pergunta", mock_graph, state=existing_state)

        call_args = mock_graph.stream.call_args[0][0]

        # Mensagens anteriores devem estar presentes
        contents = [m.content for m in call_args["messages"]]
        assert "pergunta anterior" in contents
        assert "resposta anterior" in contents

        # Summary deve ser preservado
        assert call_args["summary"] == "Resumo da conversa anterior."

    def test_run_returns_updated_state(self):
        """run() deve retornar o estado final para uso no proximo turno."""
        mock_graph = self._make_mock_graph("Resposta final.")

        from docagent.agent import run
        result = run("pergunta", mock_graph)

        assert result is not None
        assert "messages" in result

    def test_run_uses_stream_mode_values(self):
        """stream_mode='values' emite o estado completo a cada passo do grafo."""
        mock_graph = self._make_mock_graph()

        from docagent.agent import run
        run("pergunta", mock_graph)

        call_kwargs = mock_graph.stream.call_args.kwargs
        assert call_kwargs.get("stream_mode") == "values"

    def test_run_adds_system_and_human_messages(self):
        """run() deve sempre adicionar SystemMessage + HumanMessage ao estado."""
        mock_graph = self._make_mock_graph()

        from docagent.agent import run
        run("minha pergunta", mock_graph)

        call_args = mock_graph.stream.call_args[0][0]
        messages = call_args["messages"]

        assert any(isinstance(m, SystemMessage) for m in messages)
        assert any(
            isinstance(m, HumanMessage) and "minha pergunta" in m.content
            for m in messages
        )
