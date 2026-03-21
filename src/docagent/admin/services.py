from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.admin.models import Admin
from docagent.admin.schemas import AdminCreate
from docagent.auth.security import get_password_hash
from docagent.database import AsyncDBSession


class AdminService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, admin_id: int) -> Admin | None:
        return await self.session.get(Admin, admin_id)

    async def get_by_username(self, username: str) -> Admin | None:
        result = await self.session.execute(
            select(Admin).where(Admin.username == username)
        )
        return result.scalar_one_or_none()

    async def get_all(self) -> list[Admin]:
        result = await self.session.execute(select(Admin).order_by(Admin.id))
        return list(result.scalars().all())

    async def create(self, data: AdminCreate) -> Admin:
        admin = Admin(
            username=data.username,
            email=data.email,
            password=get_password_hash(data.password),
            nome=data.nome,
        )
        self.session.add(admin)
        await self.session.flush()
        await self.session.refresh(admin)
        return admin


def get_admin_service(session: AsyncDBSession) -> AdminService:
    return AdminService(session)


AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]
