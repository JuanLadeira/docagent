"""
Audit Log — Fase 21c.

Registra todas as ações administrativas e de segurança relevantes.
"""
import enum
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from docagent.database import Base


class ActorTipo(str, enum.Enum):
    ADMIN = "admin"
    USUARIO = "usuario"


class AuditLog(Base):
    __tablename__ = "audit_log"

    # Quem fez
    actor_tipo: Mapped[ActorTipo] = mapped_column(
        Enum(ActorTipo, name="actortipo"), nullable=False
    )
    actor_id: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_username: Mapped[str] = mapped_column(String(100), nullable=False)
    tenant_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tenant.id", ondelete="SET NULL"), nullable=True
    )

    # O que fez
    acao: Mapped[str] = mapped_column(String(100), nullable=False)
    recurso_tipo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    recurso_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Detalhes
    dados_antes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    dados_depois: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_origem: Mapped[str | None] = mapped_column(String(45), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
