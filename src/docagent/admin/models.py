from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from docagent.database import Base


class Admin(Base):
    """Global admin entity — separate from tenant users."""

    __tablename__ = "admin"

    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
