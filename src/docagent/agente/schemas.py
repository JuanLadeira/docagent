from datetime import datetime

from pydantic import BaseModel


class AgenteCreate(BaseModel):
    nome: str
    descricao: str = ""
    system_prompt: str | None = None
    skill_names: list[str] = []
    ativo: bool = True


class AgenteUpdate(BaseModel):
    nome: str | None = None
    descricao: str | None = None
    system_prompt: str | None = None
    skill_names: list[str] | None = None
    ativo: bool | None = None


class AgentePublic(BaseModel):
    id: int
    nome: str
    descricao: str
    system_prompt: str | None
    skill_names: list[str]
    ativo: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
