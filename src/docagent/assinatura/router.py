from fastapi import APIRouter, HTTPException, status

from docagent.assinatura.schemas import (
    AssinaturaCreate,
    AssinaturaPublic,
    AssinaturaStatusResponse,
    UsoAtualResponse,
)
from docagent.assinatura.services import AssinaturaServiceDep
from docagent.auth.current_user import CurrentUser
from docagent.plano.services import PlanoServiceDep

router = APIRouter(prefix="/api/assinaturas", tags=["Assinaturas"])


@router.get("/me", response_model=AssinaturaStatusResponse)
async def get_minha_assinatura(
    current_user: CurrentUser,
    service: AssinaturaServiceDep,
):
    assinatura = await service.get_by_tenant(current_user.tenant_id)
    if not assinatura:
        return AssinaturaStatusResponse(assinatura=None)
    return AssinaturaStatusResponse(
        assinatura=AssinaturaPublic.from_orm_with_plano(assinatura)
    )


@router.get("/me/uso", response_model=UsoAtualResponse)
async def get_uso_atual(
    current_user: CurrentUser,
    service: AssinaturaServiceDep,
):
    uso = await service.uso_atual(current_user.tenant_id)
    return UsoAtualResponse(**uso)


@router.post("/", response_model=AssinaturaPublic, status_code=status.HTTP_201_CREATED)
async def criar_ou_atualizar_assinatura(
    data: AssinaturaCreate,
    current_user: CurrentUser,
    service: AssinaturaServiceDep,
    plano_service: PlanoServiceDep,
):
    plano = await plano_service.get_by_id(data.plano_id)
    if not plano:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")

    assinatura = await service.criar(current_user.tenant_id, data.plano_id)
    return AssinaturaPublic.from_orm_with_plano(assinatura)
