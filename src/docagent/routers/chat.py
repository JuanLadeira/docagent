"""
Fase 5 — Router FastAPI para chat, health e session.

Endpoints sem logica de negocio — delega tudo ao ChatService injetado.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from docagent.schemas.chat import ChatRequest, HealthResponse
from docagent.services.chat_service import ChatService
from docagent.dependencies import get_chat_service

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/chat")
def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
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
    service: ChatService = Depends(get_chat_service),
) -> dict:
    if not service.delete_session(session_id):
        raise HTTPException(
            status_code=404,
            detail=f"Sessao '{session_id}' nao encontrada.",
        )
    return {"status": "cleared", "session_id": session_id}
