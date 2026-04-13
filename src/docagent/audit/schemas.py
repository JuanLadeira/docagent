from datetime import datetime
from typing import Any

from pydantic import BaseModel

from docagent.audit.models import ActorTipo


class AuditLogPublic(BaseModel):
    id: int
    actor_tipo: ActorTipo
    actor_id: int
    actor_username: str
    tenant_id: int | None
    acao: str
    recurso_tipo: str | None
    recurso_id: int | None
    dados_antes: dict | None
    dados_depois: dict | None
    ip_origem: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogPublic]
    total: int
    page: int
    page_size: int
    has_more: bool
