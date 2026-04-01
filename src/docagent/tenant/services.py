from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.database import AsyncDBSession
from docagent.tenant.models import Tenant
from docagent.tenant.schemas import TenantCreate, TenantLlmConfigUpdate, TenantUpdate


class TenantService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> list[Tenant]:
        result = await self.session.execute(select(Tenant).order_by(Tenant.id))
        return list(result.scalars().all())

    async def get_by_id(self, tenant_id: int) -> Tenant | None:
        return await self.session.get(Tenant, tenant_id)

    async def create(self, data: TenantCreate) -> Tenant:
        tenant = Tenant(
            nome=data.nome,
            descricao=data.descricao,
        )
        self.session.add(tenant)
        await self.session.flush()
        await self.session.refresh(tenant)
        return tenant

    async def update(self, tenant_id: int, data: TenantUpdate) -> Tenant | None:
        tenant = await self.get_by_id(tenant_id)
        if not tenant:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(tenant, key, value)

        await self.session.flush()
        await self.session.refresh(tenant)
        return tenant

    async def update_llm_config(self, tenant: Tenant, data: TenantLlmConfigUpdate) -> Tenant:
        if data.llm_provider is not None:
            tenant.llm_provider = data.llm_provider or None
        if data.llm_model is not None:
            tenant.llm_model = data.llm_model or None
        if data.llm_api_key is not None:
            tenant.llm_api_key = data.llm_api_key or None
        await self.session.flush()
        return tenant

    async def delete(self, tenant_id: int) -> bool:
        tenant = await self.get_by_id(tenant_id)
        if not tenant:
            return False

        await self.session.delete(tenant)
        await self.session.flush()
        return True


def get_tenant_service(session: AsyncDBSession) -> TenantService:
    return TenantService(session)


TenantServiceDep = Annotated[TenantService, Depends(get_tenant_service)]
