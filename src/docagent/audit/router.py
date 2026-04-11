"""
Router de Audit Log — Fase 21c.
Acessível apenas por admins autenticados.
"""
from fastapi import APIRouter, Query

from docagent.admin.current_admin import CurrentAdmin
from docagent.audit.models import ActorTipo
from docagent.audit.schemas import AuditLogListResponse, AuditLogPublic
from docagent.audit.services import AuditService
from docagent.database import AsyncDBSession

router = APIRouter(prefix="/api/admin/audit-logs", tags=["Audit"])


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    _: CurrentAdmin,
    db: AsyncDBSession,
    actor_id: int | None = Query(None),
    actor_tipo: ActorTipo | None = Query(None),
    acao: str | None = Query(None),
    recurso_tipo: str | None = Query(None),
    tenant_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    items, total = await AuditService.listar(
        db,
        actor_id=actor_id,
        actor_tipo=actor_tipo,
        acao=acao,
        recurso_tipo=recurso_tipo,
        tenant_id=tenant_id,
        page=page,
        page_size=page_size,
    )
    return AuditLogListResponse(
        items=[AuditLogPublic.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )
