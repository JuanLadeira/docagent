from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from docagent.database import Base


class SystemConfig(Base):
    """Configurações globais do sistema em formato chave-valor."""

    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    value: Mapped[str | None] = mapped_column(String(500), nullable=True)
