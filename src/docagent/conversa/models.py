"""
Fase 19 — Modelos de persistência de histórico de conversas.
"""
from enum import Enum

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from docagent.database import Base


class MensagemRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class Conversa(Base):
    __tablename__ = "conversa"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False)
    agente_id: Mapped[int] = mapped_column(ForeignKey("agente.id", ondelete="CASCADE"), nullable=False)
    titulo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    arquivada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    mensagens: Mapped[list["MensagemConversa"]] = relationship(
        "MensagemConversa",
        back_populates="conversa",
        cascade="all, delete-orphan",
        order_by="MensagemConversa.created_at",
    )


class MensagemConversa(Base):
    __tablename__ = "mensagem_conversa"

    conversa_id: Mapped[int] = mapped_column(
        ForeignKey("conversa.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tokens_entrada: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_saida: Mapped[int | None] = mapped_column(Integer, nullable=True)

    conversa: Mapped["Conversa"] = relationship("Conversa", back_populates="mensagens")
