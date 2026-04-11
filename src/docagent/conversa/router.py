"""
Fase 19 — Router para gerenciamento de conversas.

Endpoints:
  GET    /api/chat/conversas          — lista paginada
  GET    /api/chat/conversas/{id}     — conversa com mensagens
  DELETE /api/chat/conversas/{id}     — soft delete (arquivar)
  POST   /api/chat/conversas/{id}/restaurar
"""
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from docagent.auth.current_user import CurrentUser
from docagent.conversa.models import MensagemConversa, MensagemRole
from docagent.conversa.schemas import (
    ConversaDetalhada,
    ConversaListResponse,
    ConversaPublic,
    MensagemConversaPublic,
)
from docagent.conversa.services import ConversaService
from docagent.database import AsyncDBSession

router = APIRouter(prefix="/api/chat/conversas", tags=["conversas"])


@router.get("", response_model=ConversaListResponse)
async def listar_conversas(
    current_user: CurrentUser,
    db: AsyncDBSession,
    agente_id: int | None = Query(None),
    arquivada: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ConversaListResponse:
    svc = ConversaService(db)
    items = await svc.listar(
        usuario_id=current_user.id,
        tenant_id=current_user.tenant_id,
        agente_id=agente_id,
        arquivada=arquivada,
        page=page,
        page_size=page_size,
    )
    todos = await svc.listar(
        usuario_id=current_user.id,
        tenant_id=current_user.tenant_id,
        agente_id=agente_id,
        arquivada=arquivada,
        page=1,
        page_size=10_000,
    )
    total = len(todos)

    public_items = []
    for c in items:
        total_msgs = await svc.contar_mensagens(c.id)
        public_items.append(
            ConversaPublic(
                id=c.id,
                agente_id=c.agente_id,
                agente_nome="[Agente]",
                titulo=c.titulo,
                created_at=c.created_at,
                updated_at=c.updated_at,
                total_mensagens=total_msgs,
            )
        )

    return ConversaListResponse(
        items=public_items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get("/{conversa_id}", response_model=ConversaDetalhada)
async def get_conversa(
    conversa_id: int,
    current_user: CurrentUser,
    db: AsyncDBSession,
) -> ConversaDetalhada:
    svc = ConversaService(db)
    conversa = await svc.get_by_id(conversa_id, tenant_id=current_user.tenant_id)
    if conversa is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")

    result = await db.execute(
        select(MensagemConversa)
        .where(MensagemConversa.conversa_id == conversa_id)
        .order_by(MensagemConversa.created_at)
    )
    mensagens_orm = result.scalars().all()
    mensagens = [
        MensagemConversaPublic(
            id=m.id,
            role=MensagemRole(m.role),
            conteudo=m.conteudo,
            tool_name=m.tool_name,
            created_at=m.created_at,
        )
        for m in mensagens_orm
    ]

    return ConversaDetalhada(
        id=conversa.id,
        agente_id=conversa.agente_id,
        agente_nome="[Agente]",
        titulo=conversa.titulo,
        created_at=conversa.created_at,
        updated_at=conversa.updated_at,
        total_mensagens=len(mensagens),
        mensagens=mensagens,
    )


@router.delete("/{conversa_id}")
async def arquivar_conversa(
    conversa_id: int,
    current_user: CurrentUser,
    db: AsyncDBSession,
) -> dict:
    svc = ConversaService(db)
    conversa = await svc.get_by_id(conversa_id, tenant_id=current_user.tenant_id)
    if conversa is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    await svc.arquivar(conversa_id, current_user.tenant_id)
    return {"ok": True}


@router.post("/{conversa_id}/restaurar")
async def restaurar_conversa(
    conversa_id: int,
    current_user: CurrentUser,
    db: AsyncDBSession,
) -> dict:
    svc = ConversaService(db)
    conversa = await svc.get_by_id(conversa_id, tenant_id=current_user.tenant_id)
    if conversa is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    await svc.restaurar(conversa_id, current_user.tenant_id)
    return {"ok": True}
