from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.agente.models import Agente
from docagent.agente.schemas import AgenteCreate, AgenteUpdate
from docagent.database import AsyncDBSession


class AgenteService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self, tenant_id: int, apenas_ativos: bool = False) -> list[Agente]:
        query = select(Agente).where(Agente.tenant_id == tenant_id).order_by(Agente.id)
        if apenas_ativos:
            query = query.where(Agente.ativo.is_(True))
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, agente_id: int, tenant_id: int | None = None) -> Agente | None:
        agente = await self.session.get(Agente, agente_id)
        if agente is None:
            return None
        if tenant_id is not None and agente.tenant_id != tenant_id:
            return None
        return agente

    async def create(self, data: AgenteCreate, tenant_id: int) -> Agente:
        agente = Agente(**data.model_dump(), tenant_id=tenant_id)
        self.session.add(agente)
        await self.session.flush()
        await self.session.refresh(agente)
        return agente

    async def update(self, agente_id: int, data: AgenteUpdate, tenant_id: int) -> Agente | None:
        agente = await self.get_by_id(agente_id, tenant_id)
        if not agente:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(agente, field, value)
        await self.session.flush()
        await self.session.refresh(agente)
        return agente

    async def delete(self, agente_id: int, tenant_id: int) -> bool:
        agente = await self.get_by_id(agente_id, tenant_id)
        if not agente:
            return False
        await self.session.delete(agente)
        await self.session.flush()
        return True


def get_agente_service(session: AsyncDBSession) -> AgenteService:
    return AgenteService(session)


AgenteServiceDep = Annotated[AgenteService, Depends(get_agente_service)]
