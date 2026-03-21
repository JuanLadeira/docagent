"""
Fase 2/3 — Agente com LangGraph + memoria.

Fase 2: agente ReAct com duas tools (rag_search, web_search).
Fase 3: adiciona summarize node e injecao de contexto historico.

Ver docs/fase2-design.md e docs/fase3-design.md para os diagramas.
"""
import os
from typing import Annotated
from dotenv import load_dotenv

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from docagent.tools import TOOLS
from docagent.memory import should_summarize, summarize_history, trim_messages

load_dotenv()
console = Console()


class AgentState(TypedDict):
    """
    Estado do agente.

    messages: historico de mensagens — add_messages faz append, nao sobrescrita.
    summary:  resumo do historico antigo gerado pelo summarize node (Fase 3).
    """
    messages: Annotated[list[BaseMessage], add_messages]
    summary: str


SYSTEM_PROMPT = """\
Voce e um assistente especializado em analise de documentos. Responda SEMPRE em portugues.

Voce tem acesso a duas ferramentas:
- rag_search: use para responder perguntas sobre os documentos PDF carregados no sistema
- web_search: use para buscar informacoes atuais ou externas que nao estao nos documentos

IMPORTANTE: sempre use uma das ferramentas antes de responder. Nunca responda apenas com \
seu conhecimento pre-treinado.\
"""


def build_graph():
    """
    Monta o StateGraph do agente ReAct com memoria.

    Estrutura:
        START -> agent -> (should_continue) -> tools -> agent -> ...
                                            -> summarize -> END
    """
    llm = ChatOllama(
        model=os.getenv("LLM_MODEL", "qwen2.5:7b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0,
    )

    llm_with_tools = llm.bind_tools(TOOLS)

    def agent_node(state: AgentState) -> dict:
        """
        No do LLM: decide o proximo passo.

        Se existe um resumo do historico (Fase 3), injeta como contexto
        antes das mensagens atuais para o LLM ter memoria de longo prazo.
        """
        messages = state["messages"]
        summary = state.get("summary", "")

        if summary:
            # Injeta o resumo como contexto antes das mensagens recentes
            context_msg = HumanMessage(
                content=f"[CONTEXTO DA CONVERSA ANTERIOR]\n{summary}"
            )
            messages = [context_msg] + list(messages)

        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def summarize_node(state: AgentState) -> dict:
        """
        No de resumo (Fase 3): comprime o historico quando fica longo.

        So age quando o numero de mensagens ultrapassa o threshold.
        Caso contrario, passa direto sem modificar o estado.
        """
        messages = state["messages"]
        existing_summary = state.get("summary", "")

        if not should_summarize(messages):
            return {}

        # Mensagens a resumir: todas exceto as N mais recentes
        from docagent.memory import RECENT_MESSAGES_TO_KEEP
        from langchain_core.messages import HumanMessage as HMsg, AIMessage
        conversational = [m for m in messages if isinstance(m, (HMsg, AIMessage))]
        to_summarize = conversational[:-RECENT_MESSAGES_TO_KEEP]

        new_summary = summarize_history(to_summarize, existing_summary)
        trimmed_messages = trim_messages(messages)

        return {
            "summary": new_summary,
            "messages": trimmed_messages,
        }

    def should_continue(state: AgentState) -> str:
        """
        Aresta condicional apos o agent node.
        - Com tool_calls: executa a tool (continua o loop ReAct)
        - Sem tool_calls: resume o historico e encerra o turno
        """
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tools"
        return "summarize"

    tool_node = ToolNode(TOOLS)

    graph = StateGraph(AgentState)

    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("summarize", summarize_node)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")
    graph.add_edge("summarize", END)

    return graph.compile()


def run(question: str, graph, state: dict | None = None) -> dict:
    """
    Executa uma pergunta no agente.

    Aceita um estado anterior para manter memoria entre turnos.
    Retorna o estado atualizado para ser passado na proxima chamada.
    """
    console.print(f"\n[bold cyan]Pergunta:[/bold cyan] {question}\n")

    if state is None:
        state = {"messages": [], "summary": ""}

    # Adiciona a nova pergunta ao estado existente
    input_state = {
        **state,
        "messages": state["messages"] + [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=question),
        ],
    }

    final_state = None
    for step in graph.stream(input_state, stream_mode="values"):
        last_message = step["messages"][-1]
        last_message.pretty_print()
        final_state = step

    final_message = final_state["messages"][-1]
    console.print(
        Panel(Markdown(final_message.content), title="Resposta", border_style="green")
    )

    return final_state


def main():
    console.print("[bold]DocAgent — Agente ReAct com memoria[/bold]\n")
    console.print("[dim]Ferramentas: rag_search, web_search | Memoria: resumo automatico[/dim]\n")

    graph = build_graph()
    state = None  # estado persiste entre perguntas na mesma sessao

    console.print("[green]Agente pronto. Digite sua pergunta (ou 'sair' para encerrar).[/green]\n")

    while True:
        try:
            question = input("Pergunta: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not question or question.lower() in {"sair", "exit", "quit"}:
            break

        state = run(question, graph, state)

        if state.get("summary"):
            console.print(f"\n[dim]Resumo do historico: {state['summary'][:100]}...[/dim]")

    console.print("\n[dim]Encerrando DocAgent.[/dim]")


if __name__ == "__main__":
    main()
