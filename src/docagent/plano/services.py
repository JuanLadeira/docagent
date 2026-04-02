from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.database import AsyncDBSession
from docagent.plano.models import Plano
from docagent.plano.schemas import PlanoCreate, PlanoUpdate


class PlanoService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> list[Plano]:
        result = await self.session.execute(select(Plano).order_by(Plano.id))
        return list(result.scalars().all())

    async def get_by_id(self, plano_id: int) -> Plano | None:
        return await self.session.get(Plano, plano_id)

    async def create(self, data: PlanoCreate) -> Plano:
        plano = Plano(**data.model_dump())
        self.session.add(plano)
        await self.session.flush()
        await self.session.refresh(plano)
        return plano

    async def update(self, plano_id: int, data: PlanoUpdate) -> Plano | None:
        plano = await self.get_by_id(plano_id)
        if not plano:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(plano, key, value)
        await self.session.flush()
        await self.session.refresh(plano)
        return plano

    async def delete(self, plano_id: int) -> bool:
        plano = await self.get_by_id(plano_id)
        if not plano:
            return False
        await self.session.delete(plano)
        await self.session.flush()
        return True


def get_plano_service(session: AsyncDBSession) -> PlanoService:
    return PlanoService(session)


PlanoServiceDep = Annotated[PlanoService, Depends(get_plano_service)]
