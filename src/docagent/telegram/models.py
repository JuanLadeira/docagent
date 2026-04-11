import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from docagent.crypto import EncryptedString
from docagent.database import Base

if TYPE_CHECKING:
    from docagent.tenant.models import Tenant


class TelegramBotStatus(str, enum.Enum):
    ATIVA = "ATIVA"
    INATIVA = "INATIVA"


class TelegramInstancia(Base):
    __tablename__ = "telegram_instancia"

    bot_token: Mapped[str] = mapped_column(EncryptedString(700), unique=True, nullable=False)
    bot_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    webhook_configured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[TelegramBotStatus] = mapped_column(
        Enum(TelegramBotStatus, name="telegrambotstatus"),
        default=TelegramBotStatus.ATIVA,
        nullable=False,
    )
    cria_atendimentos: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agente_id: Mapped[int | None] = mapped_column(
        ForeignKey("agente.id", ondelete="SET NULL"), nullable=True
    )
    tenant: Mapped["Tenant"] = relationship(back_populates="telegram_instancias")
