from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from docagent.usuario.models import UsuarioRole


class UsuarioBase(BaseModel):
    username: str
    email: EmailStr
    nome: str
    tenant_id: int


class UsuarioCreate(UsuarioBase):
    password: str
    role: UsuarioRole = UsuarioRole.MEMBER


class UsuarioCreateAdmin(BaseModel):
    """Used by admin to create a user inside a tenant (tenant_id comes from the URL)."""

    username: str
    email: EmailStr
    nome: str
    password: str
    role: UsuarioRole = UsuarioRole.MEMBER


class UsuarioUpdate(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    nome: str | None = None
    password: str | None = None
    ativo: bool | None = None
    role: UsuarioRole | None = None


class UsuarioPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    nome: str
    ativo: bool
    role: UsuarioRole
    tenant_id: int
    created_at: datetime
    updated_at: datetime
