import asyncio
import json

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from docagent.atendimento.models import AtendimentoStatus
from docagent.atendimento.schemas import (
    AtendimentoCreate,
    AtendimentoDetalhe,
    AtendimentoPublic,
    MensagemPublic,
    OperadorMensagemRequest,
)
from docagent.atendimento.services import AtendimentoServiceDep
from docagent.atendimento.sse import atendimento_sse_manager
from docagent.auth.current_user import CurrentUser

router = APIRouter(
    prefix="/api/atendimentos",
    tags=["Atendimento"],
)


async def _get_atendimento_or_404(atendimento_id: int, current_user: CurrentUser, service: AtendimentoServiceDep):
    atendimento = await service.obter_por_id(atendimento_id, current_user.tenant_id)
    if not atendimento:
        raise HTTPException(status_code=404, detail="Atendimento não encontrado")
    return atendimento


@router.post("", response_model=AtendimentoPublic, status_code=status.HTTP_201_CREATED)
async def criar_atendimento(
    data: AtendimentoCreate,
    current_user: CurrentUser,
    service: AtendimentoServiceDep,
):
    atendimento, msg = await service.iniciar_conversa(
        data.instancia_id, current_user.tenant_id, data.numero, data.mensagem_inicial
    )
    if msg:
        await atendimento_sse_manager.broadcast(atendimento.id, {
            "type": "NOVA_MENSAGEM",
            "origem": "OPERADOR",
            "conteudo": msg.conteudo,
            "created_at": msg.created_at.isoformat(),
        })
    return atendimento


@router.get("", response_model=list[AtendimentoPublic])
async def listar_atendimentos(
    current_user: CurrentUser,
    service: AtendimentoServiceDep,
    status: str | None = None,
):
    status_enum = AtendimentoStatus(status) if status else None
    return await service.listar(current_user.tenant_id, status_enum)


@router.get("/{atendimento_id}", response_model=AtendimentoDetalhe)
async def obter_atendimento(
    atendimento_id: int,
    current_user: CurrentUser,
    service: AtendimentoServiceDep,
):
    return await _get_atendimento_or_404(atendimento_id, current_user, service)


@router.post("/{atendimento_id}/assumir", response_model=AtendimentoPublic)
async def assumir_atendimento(
    atendimento_id: int,
    current_user: CurrentUser,
    service: AtendimentoServiceDep,
):
    atendimento = await _get_atendimento_or_404(atendimento_id, current_user, service)
    return await service.assumir(atendimento)


@router.post("/{atendimento_id}/devolver", response_model=AtendimentoPublic)
async def devolver_atendimento(
    atendimento_id: int,
    current_user: CurrentUser,
    service: AtendimentoServiceDep,
):
    atendimento = await _get_atendimento_or_404(atendimento_id, current_user, service)
    return await service.devolver(atendimento)


@router.post("/{atendimento_id}/encerrar", response_model=AtendimentoPublic)
async def encerrar_atendimento(
    atendimento_id: int,
    current_user: CurrentUser,
    service: AtendimentoServiceDep,
):
    atendimento = await _get_atendimento_or_404(atendimento_id, current_user, service)
    return await service.encerrar(atendimento)


@router.post(
    "/{atendimento_id}/mensagens",
    response_model=MensagemPublic,
    status_code=status.HTTP_201_CREATED,
)
async def enviar_mensagem_operador(
    atendimento_id: int,
    data: OperadorMensagemRequest,
    current_user: CurrentUser,
    service: AtendimentoServiceDep,
):
    atendimento = await _get_atendimento_or_404(atendimento_id, current_user, service)
    msg = await service.enviar_mensagem_operador(atendimento, data.conteudo)
    await atendimento_sse_manager.broadcast(atendimento_id, {
        "type": "NOVA_MENSAGEM",
        "origem": "OPERADOR",
        "conteudo": data.conteudo,
        "created_at": msg.created_at.isoformat(),
    })
    return msg


@router.get("/{atendimento_id}/eventos")
async def eventos_atendimento(
    atendimento_id: int,
    current_user: CurrentUser,
    service: AtendimentoServiceDep,
):
    """Stream SSE de novas mensagens do atendimento."""
    await _get_atendimento_or_404(atendimento_id, current_user, service)

    async def generate():
        queue = await atendimento_sse_manager.subscribe(atendimento_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield 'data: {"type":"ping"}\n\n'
        finally:
            atendimento_sse_manager.unsubscribe(atendimento_id, queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
