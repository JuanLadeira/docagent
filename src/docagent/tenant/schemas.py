from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TenantBase(BaseModel):
    nome: str
    descricao: str | None = None


class TenantCreate(TenantBase):
    pass


class TenantUpdate(BaseModel):
    nome: str | None = None
    descricao: str | None = None


class TenantPublic(TenantBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
