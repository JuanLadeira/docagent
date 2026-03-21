"""
Fase 3 — Logica de memoria com resumo automatico.

Implementa o padrao ConversationSummaryBuffer manualmente como funcoes
puras, sem depender da classe ConversationSummaryBufferMemory do LangChain
(projetada para chains, nao para grafos com estado).

Ver docs/fase3-design.md para o diagrama e decisoes de design.
"""
import os
from dotenv import load_dotenv

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_ollama import ChatOllama

load_dotenv()

# Threshold: numero de mensagens no historico que dispara o resumo.
# Abaixo disso, nenhum resumo e gerado — evita overhead em conversas curtas.
SUMMARY_THRESHOLD = int(os.getenv("SUMMARY_THRESHOLD", "6"))

# Quantas mensagens recentes manter intactas apos o resumo.
RECENT_MESSAGES_TO_KEEP = int(os.getenv("RECENT_MESSAGES_TO_KEEP", "2"))

SUMMARY_PROMPT = """\
Voce e um assistente que cria resumos concisos de conversas em portugues.

Sua tarefa: condensar o historico de mensagens abaixo em um paragrafo curto,
preservando os pontos principais discutidos e as conclusoes importantes.

{resumo_anterior}

Mensagens a resumir:
{mensagens}

Escreva apenas o resumo, sem introducoes ou explicacoes adicionais."""


def should_summarize(messages: list[BaseMessage]) -> bool:
    """
    Decide se o historico deve ser resumido.
    Conta apenas mensagens Human e AI — ignora System e Tool messages.
    """
    conversational = [
        m for m in messages
        if isinstance(m, (HumanMessage, AIMessage))
    ]
    return len(conversational) > SUMMARY_THRESHOLD


def format_messages_for_summary(messages: list[BaseMessage]) -> str:
    """Formata mensagens em texto legivel para o LLM resumir."""
    lines = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            lines.append(f"Humano: {msg.content}")
        elif isinstance(msg, AIMessage) and msg.content:
            lines.append(f"Assistente: {msg.content}")
    return "\n".join(lines)


def summarize_history(
    messages: list[BaseMessage],
    existing_summary: str = "",
) -> str:
    """
    Chama o LLM para gerar um resumo do historico antigo.

    Se ja existe um resumo anterior, ele e incluido no prompt para que
    o novo resumo estenda o anterior em vez de substitui-lo.
    """
    llm = ChatOllama(
        model=os.getenv("LLM_MODEL", "qwen2.5:7b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0,
    )

    resumo_anterior = (
        f"Resumo da conversa ate agora:\n{existing_summary}\n"
        if existing_summary
        else ""
    )

    prompt = SUMMARY_PROMPT.format(
        resumo_anterior=resumo_anterior,
        mensagens=format_messages_for_summary(messages),
    )

    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content.strip()


def trim_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """
    Remove mensagens antigas apos o resumo, mantendo apenas as mais recentes.

    Preserva sempre a SystemMessage (se existir) e as N mensagens mais recentes
    do tipo Human/AI, pois sao o contexto imediato da conversa atual.
    """
    system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
    conversational = [m for m in messages if isinstance(m, (HumanMessage, AIMessage))]

    # Mantem apenas as N mensagens conversacionais mais recentes
    recent = conversational[-RECENT_MESSAGES_TO_KEEP:]

    return system_msgs + recent
