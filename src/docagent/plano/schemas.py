from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PlanoCreate(BaseModel):
    nome: str
    descricao: str = ""
    limite_agentes: int = 1
    limite_documentos: int = 10
    limite_sessoes: int = 5
    ciclo_dias: int = 30
    preco_mensal: Decimal = Decimal("0.00")
    ativo: bool = True


class PlanoUpdate(BaseModel):
    nome: str | None = None
    descricao: str | None = None
    limite_agentes: int | None = None
    limite_documentos: int | None = None
    limite_sessoes: int | None = None
    ciclo_dias: int | None = None
    preco_mensal: Decimal | None = None
    ativo: bool | None = None


class PlanoPublic(PlanoCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
