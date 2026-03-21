from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class AdminCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    nome: str


class AdminPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    nome: str
    ativo: bool
    created_at: datetime
    updated_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str
