import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from docagent.database import Base

if TYPE_CHECKING:
    from docagent.tenant.models import Tenant
    from docagent.agente.models import Agente


class ConexaoStatus(str, enum.Enum):
    CRIADA = "CRIADA"
    CONECTANDO = "CONECTANDO"
    CONECTADA = "CONECTADA"
    DESCONECTADA = "DESCONECTADA"


class WhatsappInstancia(Base):
    __tablename__ = "whatsapp_instancia"

    instance_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    status: Mapped[ConexaoStatus] = mapped_column(
        Enum(ConexaoStatus, name="conexaostatus"),
        default=ConexaoStatus.CRIADA,
        nullable=False,
    )
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False
    )
    agente_id: Mapped[int | None] = mapped_column(
        ForeignKey("agente.id", ondelete="SET NULL"), nullable=True
    )
    tenant: Mapped["Tenant"] = relationship(back_populates="whatsapp_instancias")
