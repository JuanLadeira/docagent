"""
Fase 2 — Agente com LangGraph.

Implementa o padrão ReAct (Reason + Act) usando um StateGraph com dois nós:
- agent: o LLM que decide qual tool usar
- tools: executa a tool escolhida pelo LLM

O loop continua até o LLM gerar uma resposta sem tool_calls.
Ver docs/fase2-design.md para o diagrama completo.
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

load_dotenv()
console = Console()


class AgentState(TypedDict):
    """
    Estado do agente — apenas a lista de mensagens.

    add_messages é um reducer: ao invés de sobrescrever a lista,
    ele faz append das novas mensagens. Isso é essencial para o loop
    funcionar — cada nó adiciona sua mensagem ao histórico existente.
    """
    messages: Annotated[list[BaseMessage], add_messages]


def build_graph():
    """
    Monta o StateGraph do agente ReAct.

    Estrutura:
        START → agent → (should_continue) → tools → agent → ...
                                          ↘ END
    """
    llm = ChatOllama(
        model=os.getenv("LLM_MODEL", "qwen2.5:7b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0,
    )

    # bind_tools informa ao LLM quais tools estão disponíveis e seus schemas.
    # O modelo usa isso para decidir quando e como chamar cada tool.
    llm_with_tools = llm.bind_tools(TOOLS)

    def agent_node(state: AgentState) -> dict:
        """
        Nó do LLM: recebe o histórico e decide o próximo passo.
        Retorna uma AIMessage que pode conter tool_calls ou a resposta final.
        """
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        """
        Aresta condicional: verifica se o LLM quer chamar uma tool.
        - Com tool_calls → executa a tool (continua o loop)
        - Sem tool_calls → resposta final (encerra)
        """
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tools"
        return END

    # ToolNode é um nó pré-construído do LangGraph que executa automaticamente
    # todas as tools listadas em tool_calls da última AIMessage.
    tool_node = ToolNode(TOOLS)

    graph = StateGraph(AgentState)

    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "agent")

    # Aresta condicional: após o agent node, decide se vai para tools ou END
    graph.add_conditional_edges("agent", should_continue)

    # Após executar a tool, sempre volta para o agent node
    graph.add_edge("tools", "agent")

    return graph.compile()


SYSTEM_PROMPT = """\
Você é um assistente especializado em análise de documentos. Responda SEMPRE em português.

Você tem acesso a duas ferramentas:
- rag_search: use para responder perguntas sobre os documentos PDF carregados no sistema
- web_search: use para buscar informações atuais ou externas que não estão nos documentos

IMPORTANTE: sempre use uma das ferramentas antes de responder. Nunca responda apenas com \
seu conhecimento pré-treinado.\
"""


def run(question: str, graph) -> None:
    """Executa uma pergunta no agente e exibe a resposta final."""
    console.print(f"\n[bold cyan]Pergunta:[/bold cyan] {question}\n")

    initial_state = {
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=question),
        ]
    }

    # stream_mode="values" emite o estado completo a cada passo do grafo.
    # Isso permite acompanhar o raciocínio do agente em tempo real.
    for step in graph.stream(initial_state, stream_mode="values"):
        last_message = step["messages"][-1]
        last_message.pretty_print()

    # A resposta final é a última AIMessage sem tool_calls
    final_message = step["messages"][-1]
    console.print(
        Panel(Markdown(final_message.content), title="Resposta final", border_style="green")
    )


def main():
    console.print("[bold]DocAgent — Agente ReAct com LangGraph[/bold]\n")
    console.print("[dim]Ferramentas disponíveis: rag_search, web_search[/dim]\n")

    graph = build_graph()

    console.print("[green]Agente pronto. Digite sua pergunta (ou 'sair' para encerrar).[/green]\n")

    while True:
        try:
            question = input("Pergunta: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not question or question.lower() in {"sair", "exit", "quit"}:
            break

        run(question, graph)

    console.print("\n[dim]Encerrando DocAgent.[/dim]")


if __name__ == "__main__":
    main()
