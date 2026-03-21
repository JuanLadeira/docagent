from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from docagent.database import Base


class Agente(Base):
    """Agente configurável armazenado no banco."""

    __tablename__ = "agente"

    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    descricao: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    skill_names: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    ativo: Mapped[bool] = mapped_column(default=True, nullable=False)
