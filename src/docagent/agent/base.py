"""
Fase 5 — BaseAgent: classe base abstrata para agentes LangGraph.

Define o contrato Template Method que todas as subclasses devem seguir.
Extrai a construcao do grafo para _build_graph() — funcao de modulo
que pode ser substituida em testes via patch.
"""
import os
import json
from abc import ABC, abstractmethod
from typing import Annotated, Iterator

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from docagent.agent.memory import (
    should_summarize,
    summarize_history,
    trim_messages,
    RECENT_MESSAGES_TO_KEEP,
)

load_dotenv()


class AgentState(TypedDict):
    """Estado compartilhado do agente LangGraph."""
    messages: Annotated[list[BaseMessage], add_messages]
    summary: str


def _build_graph(tools: list, system_prompt: str):
    """
    Constroi o StateGraph do agente ReAct com memoria.

    Funcao de modulo (nao metodo) para ser facilmente substituida em testes
    via patch("docagent.base_agent._build_graph").
    """
    llm = ChatOllama(
        model=os.getenv("LLM_MODEL", "qwen2.5:7b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0,
    )
    llm_with_tools = llm.bind_tools(tools) if tools else llm

    def agent_node(state: AgentState) -> dict:
        messages = state["messages"]
        summary = state.get("summary", "")

        if summary:
            context_msg = HumanMessage(
                content=f"[CONTEXTO DA CONVERSA ANTERIOR]\n{summary}"
            )
            messages = [context_msg] + list(messages)

        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def summarize_node(state: AgentState) -> dict:
        messages = state["messages"]
        existing_summary = state.get("summary", "")

        if not should_summarize(messages):
            return {}

        conversational = [m for m in messages if isinstance(m, (HumanMessage, AIMessage))]
        to_summarize = conversational[:-RECENT_MESSAGES_TO_KEEP]

        new_summary = summarize_history(to_summarize, existing_summary)
        trimmed = trim_messages(messages)

        return {"summary": new_summary, "messages": trimmed}

    def should_continue(state: AgentState) -> str:
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tools"
        return "summarize"

    tool_node = ToolNode(tools) if tools else ToolNode([])

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("summarize", summarize_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")
    graph.add_edge("summarize", END)

    return graph.compile()


class BaseAgent(ABC):
    """
    Classe base abstrata para agentes LangGraph.

    Subclasses devem implementar as propriedades abstratas `tools` e
    `system_prompt`. O metodo build() constroi o grafo interno usando
    _build_graph(). Os metodos run() e stream() executam o agente.
    """

    def __init__(self):
        self._graph = None
        self.last_state: dict | None = None

    @property
    @abstractmethod
    def tools(self) -> list: ...

    @property
    @abstractmethod
    def system_prompt(self) -> str: ...

    def build(self) -> "BaseAgent":
        """Constroi o grafo interno. Retorna self para encadeamento."""
        self._graph = _build_graph(self.tools, self.system_prompt)
        return self

    def run(self, question: str, state: dict | None = None) -> dict:
        """Executa uma pergunta e retorna o estado final."""
        if self._graph is None:
            raise RuntimeError("Chame build() antes de run().")

        if state is None:
            state = {"messages": [], "summary": ""}

        input_state = {
            **state,
            "messages": list(state["messages"]) + [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=question),
            ],
        }

        final_state = None
        for step in self._graph.stream(input_state, stream_mode="values"):
            final_state = step

        self.last_state = final_state
        return final_state

    def stream(self, question: str, state: dict | None = None) -> Iterator[str]:
        """Executa o agente e emite eventos no formato SSE."""
        if self._graph is None:
            raise RuntimeError("Chame build() antes de stream().")

        if state is None:
            state = {"messages": [], "summary": ""}

        input_state = {
            **state,
            "messages": list(state["messages"]) + [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=question),
            ],
        }

        final_state = None
        for step in self._graph.stream(input_state, stream_mode="values"):
            last_msg = step["messages"][-1]
            content = getattr(last_msg, "content", "")
            tool_calls = getattr(last_msg, "tool_calls", [])

            is_final_answer = (
                isinstance(last_msg, AIMessage)
                and not tool_calls
                and bool(content)
            )

            if not is_final_answer:
                if tool_calls:
                    tool_names = ", ".join(tc["name"] for tc in tool_calls)
                    step_content = f"Buscando com: {tool_names}..."
                elif content:
                    step_content = content
                else:
                    step_content = None

                if step_content:
                    yield f"data: {json.dumps({'type': 'step', 'content': step_content})}\n\n"

            final_state = step

        if final_state:
            last_msg = final_state["messages"][-1]
            answer_content = getattr(last_msg, "content", "")
            if answer_content:
                yield f"data: {json.dumps({'type': 'answer', 'content': answer_content})}\n\n"

        self.last_state = final_state
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
