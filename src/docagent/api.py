"""
Fase 4 — API FastAPI com streaming SSE e gerenciamento de sessao.

Endpoints:
- GET  /health                  → status da API
- POST /chat                    → pergunta ao agente com resposta em SSE
- DELETE /session/{session_id}  → limpa o historico de uma sessao

Ver docs/fase4-design.md para o design completo.
"""
import os
import json
from typing import Iterator
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from docagent.agent import build_graph, SYSTEM_PROMPT

load_dotenv()

# Configura LangSmith automaticamente se a chave estiver presente.
# O LangChain/LangGraph instrumenta os passos do agente sem mudanca de codigo.
if os.getenv("LANGSMITH_API_KEY"):
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGSMITH_PROJECT", "docagent")

app = FastAPI(title="DocAgent API", version="1.0.0")

# Armazenamento de sessoes em memoria: session_id → AgentState
# Em producao, substituir por Redis ou banco de dados.
sessions: dict[str, dict] = {}


class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"

    @field_validator("question")
    @classmethod
    def question_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("question must not be empty")
        return v


def _generate_sse(question: str, session_id: str) -> Iterator[str]:
    """
    Generator SSE — itera sobre os passos do grafo e emite eventos.

    Tipos de eventos:
    - step:   mensagem intermediaria (tool calls, resultados de tools)
    - answer: resposta final do agente
    - done:   sinaliza fim do stream
    """
    # build_graph() e chamado aqui (nao no modulo) para permitir
    # que os testes substituam a implementacao via patch.
    graph = build_graph()

    state = sessions.get(session_id, {"messages": [], "summary": ""})

    input_state = {
        **state,
        "messages": list(state["messages"]) + [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=question),
        ],
    }

    final_state = None

    for step in graph.stream(input_state, stream_mode="values"):
        last_msg = step["messages"][-1]
        content = getattr(last_msg, "content", "")
        tool_calls = getattr(last_msg, "tool_calls", [])

        is_final_answer = (
            isinstance(last_msg, AIMessage)
            and not tool_calls
            and bool(content)
        )

        if not is_final_answer:
            # Mensagens intermediarias: formata tool calls ou conteudo parcial
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

    # Emite a resposta final e atualiza a sessao
    if final_state:
        last_msg = final_state["messages"][-1]
        answer_content = getattr(last_msg, "content", "")
        if answer_content:
            yield f"data: {json.dumps({'type': 'answer', 'content': answer_content})}\n\n"
        sessions[session_id] = final_state

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        _generate_sse(request.question, request.session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.delete("/session/{session_id}")
def delete_session(session_id: str) -> dict:
    if session_id not in sessions:
        raise HTTPException(
            status_code=404,
            detail=f"Sessao '{session_id}' nao encontrada.",
        )
    del sessions[session_id]
    return {"status": "cleared", "session_id": session_id}
