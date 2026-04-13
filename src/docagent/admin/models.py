from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from docagent.crypto import EncryptedString
from docagent.database import Base


class Admin(Base):
    """Global admin entity — separate from tenant users."""

    __tablename__ = "admin"

    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 2FA — TOTP (Fase 21d)
    # Secret criptografado com Fernet; null se 2FA não configurado
    totp_secret: Mapped[str | None] = mapped_column(EncryptedString(700), nullable=True)
    totp_habilitado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
