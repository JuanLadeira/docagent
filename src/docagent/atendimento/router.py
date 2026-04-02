import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from jwt import DecodeError, ExpiredSignatureError, decode
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from docagent.atendimento.models import Atendimento, AtendimentoStatus, CanalAtendimento, Contato
from docagent.atendimento.schemas import (
    AtendimentoCreate,
    AtendimentoDetalhe,
    AtendimentoPublic,
    ContatoCreate,
    ContatoDetalhe,
    ContatoPublic,
    ContatoUpdate,
    MensagemPublic,
    OperadorMensagemRequest,
)
from docagent.atendimento.services import AtendimentoServiceDep
from docagent.atendimento.sse import atendimento_lista_sse_manager, atendimento_sse_manager
from docagent.auth.current_user import CurrentUser
from docagent.database import AsyncDBSession, AsyncSessionLocal
from docagent.settings import Settings
from docagent.telegram.atendimento_service import TelegramAtendimentoServiceDep
from docagent.usuario.models import Usuario
from docagent.whatsapp.atendimento_service import WhatsappAtendimentoServiceDep

_settings = Settings()
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


async def _resolve_tenant_sse(token: str = Depends(_oauth2_scheme)) -> int:
    """Valida o JWT e retorna tenant_id usando uma sessão de curta duração.
    Não mantém nenhuma conexão de banco aberta durante o stream SSE."""
    try:
        payload = decode(token, _settings.SECRET_KEY, algorithms=[_settings.ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Token inválido")
    except (DecodeError, ExpiredSignatureError):
        raise HTTPException(status_code=401, detail="Token inválido")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Usuario).where(Usuario.username == username))
        user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return user.tenant_id


TenantIdSse = Annotated[int, Depends(_resolve_tenant_sse)]

router = APIRouter(
    prefix="/api/atendimentos",
    tags=["Atendimento"],
)


async def _get_atendimento_or_404(atendimento_id: int, current_user: CurrentUser, service: AtendimentoServiceDep):
    atendimento = await service.obter_por_id(atendimento_id, current_user.tenant_id)
    if not atendimento:
        raise HTTPException(status_code=404, detail="Atendimento não encontrado")
    return atendimento


# ── SSE: lista de atendimentos (tenant-nível) ─────────────────────────────────
# IMPORTANTE: rotas literais (/eventos, /contatos) devem vir ANTES de /{id}

@router.get("/eventos")
async def eventos_lista(tenant_id: TenantIdSse):
    """Stream SSE de novos atendimentos e mudanças de status (para a lista)."""
    async def generate():
        queue = await atendimento_lista_sse_manager.subscribe(tenant_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield 'data: {"type":"ping"}\n\n'
        finally:
            atendimento_lista_sse_manager.unsubscribe(tenant_id, queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── CRUD de contatos ──────────────────────────────────────────────────────────
# Devem vir antes de /{atendimento_id} para evitar conflito de rota

@router.post("/contatos", response_model=ContatoPublic, status_code=status.HTTP_201_CREATED)
async def criar_contato(
    data: ContatoCreate,
    current_user: CurrentUser,
    session: AsyncDBSession,
):
    contato = Contato(
        numero=data.numero,
        nome=data.nome,
        email=data.email,
        notas=data.notas,
        instancia_id=data.instancia_id,
        tenant_id=current_user.tenant_id,
    )
    session.add(contato)
    await session.flush()
    await session.refresh(contato)

    # Vincular atendimentos existentes desse número à instância
    result = await session.execute(
        select(Atendimento).where(
            Atendimento.numero == data.numero,
            Atendimento.instancia_id == data.instancia_id,
            Atendimento.tenant_id == current_user.tenant_id,
            Atendimento.contato_id.is_(None),
        )
    )
    atendimentos_vinculados = result.scalars().all()
    for at in atendimentos_vinculados:
        at.contato_id = contato.id
        at.nome_contato = contato.nome

    await session.flush()

    for at in atendimentos_vinculados:
        at_public = AtendimentoPublic.model_validate(at)
        await atendimento_lista_sse_manager.broadcast(current_user.tenant_id, {
            "type": "ATENDIMENTO_ATUALIZADO",
            "atendimento": at_public.model_dump(mode="json"),
        })

    return contato


@router.get("/contatos", response_model=list[ContatoPublic])
async def listar_contatos(
    current_user: CurrentUser,
    session: AsyncDBSession,
):
    result = await session.execute(
        select(Contato).where(Contato.tenant_id == current_user.tenant_id)
    )
    return list(result.scalars().all())


@router.get("/contatos/{contato_id}", response_model=ContatoDetalhe)
async def obter_contato(
    contato_id: int,
    current_user: CurrentUser,
    session: AsyncDBSession,
):
    result = await session.execute(
        select(Contato)
        .options(selectinload(Contato.atendimentos))
        .where(Contato.id == contato_id, Contato.tenant_id == current_user.tenant_id)
    )
    contato = result.scalar_one_or_none()
    if not contato:
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    return contato


@router.patch("/contatos/{contato_id}", response_model=ContatoPublic)
async def atualizar_contato(
    contato_id: int,
    data: ContatoUpdate,
    current_user: CurrentUser,
    session: AsyncDBSession,
):
    result = await session.execute(
        select(Contato).where(Contato.id == contato_id, Contato.tenant_id == current_user.tenant_id)
    )
    contato = result.scalar_one_or_none()
    if not contato:
        raise HTTPException(status_code=404, detail="Contato não encontrado")

    if data.nome is not None:
        contato.nome = data.nome
    if data.email is not None:
        contato.email = data.email
    if data.notas is not None:
        contato.notas = data.notas

    await session.flush()
    return contato


# ── CRUD de atendimentos ──────────────────────────────────────────────────────

@router.post("", response_model=AtendimentoPublic, status_code=status.HTTP_201_CREATED)
async def criar_atendimento(
    data: AtendimentoCreate,
    current_user: CurrentUser,
    wa_service: WhatsappAtendimentoServiceDep,
):
    atendimento, msg = await wa_service.iniciar_conversa(
        data.instancia_id, current_user.tenant_id, data.numero, data.mensagem_inicial
    )
    if msg:
        await atendimento_sse_manager.broadcast(atendimento.id, {
            "type": "NOVA_MENSAGEM",
            "origem": "OPERADOR",
            "conteudo": msg.conteudo,
            "created_at": msg.created_at.isoformat(),
        })
    at_public = AtendimentoPublic.model_validate(atendimento)
    await atendimento_lista_sse_manager.broadcast(current_user.tenant_id, {
        "type": "NOVO_ATENDIMENTO",
        "atendimento": at_public.model_dump(mode="json"),
    })
    return atendimento


@router.get("", response_model=list[AtendimentoPublic])
async def listar_atendimentos(
    current_user: CurrentUser,
    service: AtendimentoServiceDep,
    status: str | None = Query(None),
    canal: str | None = Query(None),
):
    status_enum = AtendimentoStatus(status) if status else None
    canal_enum = CanalAtendimento(canal) if canal else None
    return await service.listar(current_user.tenant_id, status_enum, canal_enum)


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
    atendimento = await service.assumir(atendimento, current_user.id, current_user.nome)
    at_public = AtendimentoPublic.model_validate(atendimento)
    await atendimento_lista_sse_manager.broadcast(current_user.tenant_id, {
        "type": "ATENDIMENTO_ATUALIZADO",
        "atendimento": at_public.model_dump(mode="json"),
    })
    return atendimento


@router.post("/{atendimento_id}/devolver", response_model=AtendimentoPublic)
async def devolver_atendimento(
    atendimento_id: int,
    current_user: CurrentUser,
    service: AtendimentoServiceDep,
):
    atendimento = await _get_atendimento_or_404(atendimento_id, current_user, service)
    atendimento = await service.devolver(atendimento)
    at_public = AtendimentoPublic.model_validate(atendimento)
    await atendimento_lista_sse_manager.broadcast(current_user.tenant_id, {
        "type": "ATENDIMENTO_ATUALIZADO",
        "atendimento": at_public.model_dump(mode="json"),
    })
    return atendimento


@router.post("/{atendimento_id}/encerrar", response_model=AtendimentoPublic)
async def encerrar_atendimento(
    atendimento_id: int,
    current_user: CurrentUser,
    service: AtendimentoServiceDep,
):
    atendimento = await _get_atendimento_or_404(atendimento_id, current_user, service)
    atendimento = await service.encerrar(atendimento)
    at_public = AtendimentoPublic.model_validate(atendimento)
    await atendimento_lista_sse_manager.broadcast(current_user.tenant_id, {
        "type": "ATENDIMENTO_ATUALIZADO",
        "atendimento": at_public.model_dump(mode="json"),
    })
    return atendimento


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
    wa_service: WhatsappAtendimentoServiceDep,
    tg_service: TelegramAtendimentoServiceDep,
):
    atendimento = await _get_atendimento_or_404(atendimento_id, current_user, service)
    if atendimento.status != AtendimentoStatus.HUMANO:
        raise HTTPException(
            status_code=400,
            detail="Só é possível enviar mensagem quando o atendimento está em modo HUMANO",
        )

    if atendimento.canal == CanalAtendimento.TELEGRAM:
        msg = await tg_service.enviar_mensagem_operador(atendimento, data.conteudo)
    else:
        msg = await wa_service.enviar_mensagem_operador(atendimento, data.conteudo)

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
    tenant_id: TenantIdSse,
):
    """Stream SSE de novas mensagens do atendimento."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Atendimento).where(
                Atendimento.id == atendimento_id,
                Atendimento.tenant_id == tenant_id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Atendimento não encontrado")

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
