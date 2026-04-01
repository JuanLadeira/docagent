from fastapi import APIRouter, HTTPException, status

from docagent.auth.current_user import CurrentUser
from docagent.tenant.schemas import TenantCreate, TenantLlmConfigUpdate, TenantPublic, TenantUpdate
from docagent.tenant.services import TenantServiceDep

router = APIRouter(
    prefix="/api/tenants",
    tags=["Tenants"],
    responses={404: {"description": "Nao encontrado"}},
)


@router.get("/", response_model=list[TenantPublic])
async def list_tenants(service: TenantServiceDep):
    return await service.get_all()


@router.get("/{tenant_id}", response_model=TenantPublic)
async def get_tenant(tenant_id: int, service: TenantServiceDep):
    tenant = await service.get_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant nao encontrado")
    return tenant


@router.post("/", response_model=TenantPublic, status_code=status.HTTP_201_CREATED)
async def create_tenant(data: TenantCreate, service: TenantServiceDep):
    return await service.create(data)


@router.put("/{tenant_id}", response_model=TenantPublic)
async def update_tenant(tenant_id: int, data: TenantUpdate, service: TenantServiceDep):
    tenant = await service.update(tenant_id, data)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant nao encontrado")
    return tenant


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(tenant_id: int, service: TenantServiceDep):
    deleted = await service.delete(tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tenant nao encontrado")


# ── Configuração de LLM pelo tenant owner ─────────────────────────────────────

class _LlmConfigResponse(TenantLlmConfigUpdate):
    llm_api_key_set: bool = False
    llm_api_key: str | None = None  # nunca retorna o valor real


@router.get("/me/llm-config")
async def get_my_llm_config(current_user: CurrentUser, service: TenantServiceDep):
    """Retorna a configuração LLM do tenant atual (owner apenas)."""
    if current_user.role != "OWNER":
        raise HTTPException(status_code=403, detail="Apenas owners podem acessar esta configuração")
    tenant = await service.get_by_id(current_user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return {
        "llm_provider": tenant.llm_provider,
        "llm_model": tenant.llm_model,
        "llm_api_key": None,
        "llm_api_key_set": bool(tenant.llm_api_key),
    }


@router.put("/me/llm-config")
async def update_my_llm_config(
    data: TenantLlmConfigUpdate,
    current_user: CurrentUser,
    service: TenantServiceDep,
):
    """Atualiza a configuração LLM do tenant atual (owner apenas)."""
    if current_user.role != "OWNER":
        raise HTTPException(status_code=403, detail="Apenas owners podem alterar esta configuração")
    tenant = await service.get_by_id(current_user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    await service.update_llm_config(tenant, data)
    return {
        "llm_provider": tenant.llm_provider,
        "llm_model": tenant.llm_model,
        "llm_api_key": None,
        "llm_api_key_set": bool(tenant.llm_api_key),
    }
