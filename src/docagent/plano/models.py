from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from docagent.database import Base

if TYPE_CHECKING:
    from docagent.assinatura.models import Assinatura


class Plano(Base):
    __tablename__ = "planos"

    nome: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    descricao: Mapped[str] = mapped_column(String(500), default="")
    limite_documentos: Mapped[int] = mapped_column(default=10)
    limite_sessoes: Mapped[int] = mapped_column(default=5)
    preco_mensal: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    ativo: Mapped[bool] = mapped_column(default=True)

    assinaturas: Mapped[list["Assinatura"]] = relationship(
        back_populates="plano",
        lazy="selectin",
    )
