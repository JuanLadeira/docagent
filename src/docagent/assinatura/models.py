from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from docagent.database import Base

if TYPE_CHECKING:
    from docagent.plano.models import Plano
    from docagent.tenant.models import Tenant


class Assinatura(Base):
    __tablename__ = "assinatura"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_assinatura_tenant"),
    )

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    plano_id: Mapped[int] = mapped_column(ForeignKey("planos.id"), nullable=False)
    ativo: Mapped[bool] = mapped_column(default=True)
    data_inicio: Mapped[datetime] = mapped_column(nullable=False)
    data_proxima_renovacao: Mapped[datetime] = mapped_column(nullable=False)
    stripe_subscription_id: Mapped[str | None] = mapped_column(nullable=True)

    plano: Mapped["Plano"] = relationship(back_populates="assinaturas", lazy="selectin")
    tenant: Mapped["Tenant"] = relationship(lazy="selectin")
