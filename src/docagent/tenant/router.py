from fastapi import APIRouter, HTTPException, status

from docagent.tenant.schemas import TenantCreate, TenantPublic, TenantUpdate
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
