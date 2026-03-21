from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.auth.security import get_password_hash
from docagent.database import AsyncDBSession
from docagent.usuario.models import Usuario
from docagent.usuario.schemas import UsuarioCreate, UsuarioUpdate


class UsuarioService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self, tenant_id: int | None = None) -> list[Usuario]:
        query = select(Usuario).order_by(Usuario.id)
        if tenant_id:
            query = query.where(Usuario.tenant_id == tenant_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, usuario_id: int) -> Usuario | None:
        return await self.session.get(Usuario, usuario_id)

    async def get_by_username(self, username: str) -> Usuario | None:
        result = await self.session.execute(
            select(Usuario).where(Usuario.username == username)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Usuario | None:
        result = await self.session.execute(
            select(Usuario).where(Usuario.email == email)
        )
        return result.scalar_one_or_none()

    async def create(self, data: UsuarioCreate) -> Usuario:
        usuario = Usuario(
            username=data.username,
            email=data.email,
            password=get_password_hash(data.password),
            nome=data.nome,
            tenant_id=data.tenant_id,
            role=data.role,
        )
        self.session.add(usuario)
        await self.session.flush()
        await self.session.refresh(usuario)
        return usuario

    async def update(self, usuario_id: int, data: UsuarioUpdate) -> Usuario | None:
        usuario = await self.get_by_id(usuario_id)
        if not usuario:
            return None

        update_data = data.model_dump(exclude_unset=True)
        if "password" in update_data and update_data["password"]:
            update_data["password"] = get_password_hash(update_data["password"])

        for key, value in update_data.items():
            setattr(usuario, key, value)

        await self.session.flush()
        await self.session.refresh(usuario)
        return usuario

    async def delete(self, usuario_id: int) -> bool:
        usuario = await self.get_by_id(usuario_id)
        if not usuario:
            return False

        await self.session.delete(usuario)
        return True


def get_usuario_service(session: AsyncDBSession) -> UsuarioService:
    return UsuarioService(session)


UsuarioServiceDep = Annotated[UsuarioService, Depends(get_usuario_service)]
