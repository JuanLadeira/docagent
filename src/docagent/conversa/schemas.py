"""
Fase 19 — Schemas Pydantic para conversas e mensagens.
"""
from datetime import datetime

from pydantic import BaseModel

from docagent.conversa.models import MensagemRole


class MensagemConversaPublic(BaseModel):
    id: int
    role: MensagemRole
    conteudo: str
    tool_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversaPublic(BaseModel):
    id: int
    agente_id: int
    agente_nome: str
    titulo: str | None
    created_at: datetime
    updated_at: datetime
    total_mensagens: int

    model_config = {"from_attributes": True}


class ConversaDetalhada(ConversaPublic):
    mensagens: list[MensagemConversaPublic]


class ConversaListResponse(BaseModel):
    items: list[ConversaPublic]
    total: int
    page: int
    page_size: int
    has_more: bool
