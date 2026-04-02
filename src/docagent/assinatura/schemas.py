from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AssinaturaCreate(BaseModel):
    plano_id: int


class AssinaturaPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    plano_id: int
    plano_nome: str
    ativo: bool
    data_inicio: datetime
    data_proxima_renovacao: datetime
    stripe_subscription_id: str | None = None

    @classmethod
    def from_orm_with_plano(cls, assinatura) -> "AssinaturaPublic":
        return cls(
            id=assinatura.id,
            tenant_id=assinatura.tenant_id,
            plano_id=assinatura.plano_id,
            plano_nome=assinatura.plano.nome,
            ativo=assinatura.ativo,
            data_inicio=assinatura.data_inicio,
            data_proxima_renovacao=assinatura.data_proxima_renovacao,
            stripe_subscription_id=assinatura.stripe_subscription_id,
        )


class AssinaturaStatusResponse(BaseModel):
    assinatura: AssinaturaPublic | None


class UsoAtualResponse(BaseModel):
    plano: str | None
    agentes_atual: int
    agentes_limite: int | None
    documentos_atual: int
    documentos_limite: int | None
