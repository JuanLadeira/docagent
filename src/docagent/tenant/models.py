from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from docagent.database import Base

if TYPE_CHECKING:
    from docagent.usuario.models import Usuario
    from docagent.whatsapp.models import WhatsappInstancia
    from docagent.telegram.models import TelegramInstancia


class Tenant(Base):
    """Represents an organization (tenant) in the SaaS."""

    __tablename__ = "tenant"

    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    usuarios: Mapped[list["Usuario"]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    whatsapp_instancias: Mapped[list["WhatsappInstancia"]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    telegram_instancias: Mapped[list["TelegramInstancia"]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
