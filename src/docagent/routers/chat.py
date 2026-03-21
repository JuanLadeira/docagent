"""
Router FastAPI para chat, health e session.

O agente e carregado do banco de dados a partir do agent_id da requisicao.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from docagent.agente.services import AgenteServiceDep
from docagent.agents.configurable_agent import ConfigurableAgent
from docagent.agents.registry import AgentConfig
from docagent.dependencies import get_session_manager
from docagent.schemas.chat import ChatRequest, HealthResponse
from docagent.services.chat_service import ChatService
from docagent.session import SessionManager

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/chat")
async def chat(
    request: ChatRequest,
    agente_service: AgenteServiceDep,
    sessions: SessionManager = Depends(get_session_manager),
) -> StreamingResponse:
    try:
        agente_id = int(request.agent_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="agent_id deve ser um numero inteiro")

    agente = await agente_service.get_by_id(agente_id)
    if not agente or not agente.ativo:
        raise HTTPException(status_code=404, detail=f"Agente '{request.agent_id}' nao encontrado")

    config = AgentConfig(
        id=str(agente.id),
        name=agente.nome,
        description=agente.descricao,
        skill_names=agente.skill_names,
    )
    agent = ConfigurableAgent(
        config,
        system_prompt_override=agente.system_prompt or None,
    ).build()

    service = ChatService(agent, sessions)
    return StreamingResponse(
        service.stream(request.question, request.session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/session/{session_id}")
def delete_session(
    session_id: str,
    sessions: SessionManager = Depends(get_session_manager),
) -> dict:
    if not sessions.delete(session_id):
        raise HTTPException(
            status_code=404,
            detail=f"Sessao '{session_id}' nao encontrada.",
        )
    return {"status": "cleared", "session_id": session_id}
