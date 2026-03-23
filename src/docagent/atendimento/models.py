import enum

from sqlalchemy import Enum, ForeignKey, String, Text, UniqueConstraint
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


class Prioridade(str, enum.Enum):
    NORMAL = "NORMAL"
    ALTA = "ALTA"
    URGENTE = "URGENTE"


class Contato(Base):
    __tablename__ = "contato"
    __table_args__ = (
        UniqueConstraint("numero", "tenant_id", "instancia_id", name="uq_contato_numero_tenant_instancia"),
    )

    numero: Mapped[str] = mapped_column(String(50), nullable=False)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    instancia_id: Mapped[int] = mapped_column(
        ForeignKey("whatsapp_instancia.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    atendimentos: Mapped[list["Atendimento"]] = relationship(back_populates="contato")


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
    prioridade: Mapped[Prioridade] = mapped_column(
        Enum(Prioridade, name="prioridade"),
        default=Prioridade.NORMAL,
        nullable=False,
    )
    contato_id: Mapped[int | None] = mapped_column(
        ForeignKey("contato.id", ondelete="SET NULL"), nullable=True
    )
    contato: Mapped["Contato | None"] = relationship(back_populates="atendimentos")
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
