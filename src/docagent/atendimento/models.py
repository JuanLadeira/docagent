import enum

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from docagent.database import Base


class AtendimentoStatus(str, enum.Enum):
    ATIVO = "ATIVO"
    HUMANO = "HUMANO"
    ENCERRADO = "ENCERRADO"


class MensagemOrigem(str, enum.Enum):
    CONTATO = "CONTATO"
    AGENTE = "AGENTE"
    OPERADOR = "OPERADOR"


class Atendimento(Base):
    __tablename__ = "atendimento"

    numero: Mapped[str] = mapped_column(String(50), nullable=False)
    nome_contato: Mapped[str | None] = mapped_column(String(100), nullable=True)
    instancia_id: Mapped[int] = mapped_column(
        ForeignKey("whatsapp_instancia.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[AtendimentoStatus] = mapped_column(
        Enum(AtendimentoStatus, name="atendimentostatus"),
        default=AtendimentoStatus.ATIVO,
        nullable=False,
    )
    mensagens: Mapped[list["MensagemAtendimento"]] = relationship(
        back_populates="atendimento",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="MensagemAtendimento.created_at",
    )


class MensagemAtendimento(Base):
    __tablename__ = "mensagem_atendimento"

    atendimento_id: Mapped[int] = mapped_column(
        ForeignKey("atendimento.id", ondelete="CASCADE"), nullable=False
    )
    origem: Mapped[MensagemOrigem] = mapped_column(
        Enum(MensagemOrigem, name="mensagemorigem"), nullable=False
    )
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    atendimento: Mapped["Atendimento"] = relationship(back_populates="mensagens")
