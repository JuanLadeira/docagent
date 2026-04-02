from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from docagent.database import Base

if TYPE_CHECKING:
    from docagent.tenant.models import Tenant


class Agente(Base):
    """Agente configurável armazenado no banco."""

    __tablename__ = "agente"

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    descricao: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    skill_names: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    ativo: Mapped[bool] = mapped_column(default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship("Tenant")

    documentos: Mapped[list["Documento"]] = relationship(
        "Documento", back_populates="agente", cascade="all, delete-orphan"
    )


class Documento(Base):
    """Documento PDF indexado no ChromaDB para um agente específico."""

    __tablename__ = "documento"

    agente_id: Mapped[int] = mapped_column(
        ForeignKey("agente.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    agente: Mapped["Agente"] = relationship("Agente", back_populates="documentos")
