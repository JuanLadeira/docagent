"""
Testes para a logica de memoria (memory.py).

Estratégia:
- should_summarize e format_messages_for_summary sao funcoes puras — testadas diretamente.
- trim_messages e pura — testada diretamente.
- summarize_history depende do LLM — testada com mock.
"""
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

from docagent.agent.memory import (
    should_summarize,
    format_messages_for_summary,
    summarize_history,
    trim_messages,
    SUMMARY_THRESHOLD,
    RECENT_MESSAGES_TO_KEEP,
)


def make_turn(question: str, answer: str) -> list:
    """Cria um par Human/AI para facilitar a montagem de historicos nos testes."""
    return [HumanMessage(content=question), AIMessage(content=answer)]


class TestShouldSummarize:
    def test_returns_false_below_threshold(self):
        """Historico curto nao deve disparar o resumo."""
        messages = make_turn("pergunta", "resposta")  # 2 mensagens
        assert should_summarize(messages) is False

    def test_returns_true_above_threshold(self):
        """Historico longo deve disparar o resumo."""
        messages = []
        for i in range(SUMMARY_THRESHOLD):
            messages += make_turn(f"pergunta {i}", f"resposta {i}")
        # SUMMARY_THRESHOLD pares = SUMMARY_THRESHOLD * 2 mensagens > SUMMARY_THRESHOLD
        assert should_summarize(messages) is True

    def test_ignores_system_messages(self):
        """SystemMessages nao contam para o threshold."""
        system_msgs = [SystemMessage(content="instrucao")] * 10
        conv_msgs = make_turn("pergunta", "resposta")  # 2 Human/AI
        assert should_summarize(system_msgs + conv_msgs) is False

    def test_ignores_tool_messages(self):
        """ToolMessages nao contam para o threshold."""
        tool_msgs = [ToolMessage(content="resultado", tool_call_id="123")] * 10
        conv_msgs = make_turn("pergunta", "resposta")  # 2 Human/AI
        assert should_summarize(tool_msgs + conv_msgs) is False

    def test_exactly_at_threshold_returns_false(self):
        """Exatamente no threshold nao deve resumir — so acima."""
        messages = []
        # Gera exatamente SUMMARY_THRESHOLD mensagens Human (sem AI)
        for i in range(SUMMARY_THRESHOLD):
            messages.append(HumanMessage(content=f"msg {i}"))
        assert should_summarize(messages) is False


class TestFormatMessagesForSummary:
    def test_formats_human_and_ai_messages(self):
        messages = [
            HumanMessage(content="O que e RAG?"),
            AIMessage(content="RAG e uma tecnica de busca."),
        ]
        result = format_messages_for_summary(messages)
        assert "Humano: O que e RAG?" in result
        assert "Assistente: RAG e uma tecnica de busca." in result

    def test_skips_empty_ai_messages(self):
        """AIMessages vazias (apenas tool_calls) nao devem aparecer no resumo."""
        messages = [
            HumanMessage(content="pergunta"),
            AIMessage(content=""),  # tool_call sem texto
            AIMessage(content="resposta final"),
        ]
        result = format_messages_for_summary(messages)
        assert result.count("Assistente:") == 1
        assert "resposta final" in result

    def test_ignores_system_and_tool_messages(self):
        messages = [
            SystemMessage(content="instrucao do sistema"),
            ToolMessage(content="resultado da tool", tool_call_id="abc"),
            HumanMessage(content="pergunta"),
            AIMessage(content="resposta"),
        ]
        result = format_messages_for_summary(messages)
        assert "instrucao do sistema" not in result
        assert "resultado da tool" not in result
        assert "Humano: pergunta" in result


class TestTrimMessages:
    def test_keeps_only_recent_conversational_messages(self):
        """Apos o trim, so as N mensagens mais recentes devem permanecer."""
        messages = []
        for i in range(6):
            messages += make_turn(f"pergunta {i}", f"resposta {i}")

        trimmed = trim_messages(messages)
        conversational = [m for m in trimmed if isinstance(m, (HumanMessage, AIMessage))]

        assert len(conversational) == RECENT_MESSAGES_TO_KEEP

    def test_preserves_system_messages(self):
        """SystemMessages devem sempre ser preservadas apos o trim."""
        messages = [SystemMessage(content="instrucao")] + make_turn("p", "r") * 4
        trimmed = trim_messages(messages)
        system_msgs = [m for m in trimmed if isinstance(m, SystemMessage)]
        assert len(system_msgs) == 1
        assert system_msgs[0].content == "instrucao"

    def test_most_recent_messages_are_kept(self):
        """As mensagens mantidas devem ser as mais recentes, nao as mais antigas."""
        messages = (
            make_turn("antiga 1", "resposta antiga 1")
            + make_turn("antiga 2", "resposta antiga 2")
            + make_turn("recente", "resposta recente")
        )
        trimmed = trim_messages(messages)
        contents = [m.content for m in trimmed]
        assert "recente" in contents
        assert "resposta recente" in contents
        assert "antiga 1" not in contents


class TestSummarizeHistory:
    def test_calls_llm_and_returns_summary(self):
        """summarize_history deve chamar o LLM e retornar o texto do resumo."""
        messages = make_turn("O que e RAG?", "RAG e uma tecnica de busca semantica.")

        mock_response = MagicMock()
        mock_response.content = "O usuario perguntou sobre RAG e recebeu uma explicacao."

        with patch("docagent.agent.memory.ChatOllama") as MockLLM:
            mock_instance = MockLLM.return_value
            mock_instance.invoke.return_value = mock_response

            result = summarize_history(messages)

        assert result == "O usuario perguntou sobre RAG e recebeu uma explicacao."
        mock_instance.invoke.assert_called_once()

    def test_includes_existing_summary_in_prompt(self):
        """Se ja existe um resumo, ele deve aparecer no prompt enviado ao LLM."""
        messages = make_turn("nova pergunta", "nova resposta")
        existing = "O usuario perguntou sobre embeddings anteriormente."

        mock_response = MagicMock()
        mock_response.content = "Resumo estendido."

        with patch("docagent.agent.memory.ChatOllama") as MockLLM:
            mock_instance = MockLLM.return_value
            mock_instance.invoke.return_value = mock_response

            summarize_history(messages, existing_summary=existing)

        # Verifica que o resumo existente foi incluido na mensagem enviada ao LLM
        call_args = mock_instance.invoke.call_args[0][0]
        prompt_content = call_args[0].content
        assert existing in prompt_content

    def test_uses_temperature_zero(self):
        """Resumos devem ser deterministicos — temperature=0."""
        with patch("docagent.agent.memory.ChatOllama") as MockLLM:
            MockLLM.return_value.invoke.return_value = MagicMock(content="resumo")
            summarize_history([HumanMessage(content="x")])

        assert MockLLM.call_args.kwargs["temperature"] == 0
