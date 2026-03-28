from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from docagent.atendimento.models import (
    Atendimento,
    AtendimentoStatus,
    CanalAtendimento,
    MensagemAtendimento,
    MensagemOrigem,
)
from docagent.database import AsyncDBSession


class AtendimentoService:
    """Serviço base com operações canal-agnósticas: transições de status, mensagens, consultas."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def salvar_mensagem(
        self, atendimento_id: int, origem: MensagemOrigem, conteudo: str
    ) -> MensagemAtendimento:
        msg = MensagemAtendimento(
            atendimento_id=atendimento_id,
            origem=origem,
            conteudo=conteudo,
        )
        self.session.add(msg)
        await self.session.flush()
        await self.session.refresh(msg)
        return msg

    async def assumir(self, atendimento: Atendimento) -> Atendimento:
        atendimento.status = AtendimentoStatus.HUMANO
        await self.session.flush()
        await self.session.refresh(atendimento)
        return atendimento

    async def devolver(self, atendimento: Atendimento) -> Atendimento:
        atendimento.status = AtendimentoStatus.ATIVO
        await self.session.flush()
        await self.session.refresh(atendimento)
        return atendimento

    async def encerrar(self, atendimento: Atendimento) -> Atendimento:
        atendimento.status = AtendimentoStatus.ENCERRADO
        await self.session.flush()
        await self.session.refresh(atendimento)
        return atendimento

    async def obter_por_id(self, atendimento_id: int, tenant_id: int) -> Atendimento | None:
        result = await self.session.execute(
            select(Atendimento)
            .options(selectinload(Atendimento.mensagens))
            .where(
                Atendimento.id == atendimento_id,
                Atendimento.tenant_id == tenant_id,
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def listar(
        self,
        tenant_id: int,
        status: AtendimentoStatus | None = None,
        canal: CanalAtendimento | None = None,
    ) -> list[Atendimento]:
        query = select(Atendimento).where(Atendimento.tenant_id == tenant_id)
        if status:
            query = query.where(Atendimento.status == status)
        if canal:
            query = query.where(Atendimento.canal == canal)
        result = await self.session.execute(query)
        return list(result.scalars().all())


def get_atendimento_service(session: AsyncDBSession) -> AtendimentoService:
    return AtendimentoService(session)


AtendimentoServiceDep = Annotated[AtendimentoService, Depends(get_atendimento_service)]
