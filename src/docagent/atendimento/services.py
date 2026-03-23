from typing import Annotated

import httpx
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from docagent.atendimento.models import (
    Atendimento,
    AtendimentoStatus,
    MensagemAtendimento,
    MensagemOrigem,
)
from docagent.database import AsyncDBSession
from docagent.whatsapp.client import EvolutionClientDep
from docagent.whatsapp.models import WhatsappInstancia


class AtendimentoService:
    def __init__(self, session: AsyncSession, client: httpx.AsyncClient):
        self.session = session
        self.client = client

    async def criar_ou_retomar(
        self, instancia_id: int, tenant_id: int, numero: str
    ) -> Atendimento:
        """Busca atendimento ativo/humano para o número. Se não existe, cria novo."""
        result = await self.session.execute(
            select(Atendimento).where(
                Atendimento.instancia_id == instancia_id,
                Atendimento.numero == numero,
                Atendimento.status != AtendimentoStatus.ENCERRADO,
            )
        )
        atendimento = result.scalar_one_or_none()
        if atendimento:
            return atendimento

        atendimento = Atendimento(
            numero=numero,
            instancia_id=instancia_id,
            tenant_id=tenant_id,
            status=AtendimentoStatus.ATIVO,
        )
        self.session.add(atendimento)
        await self.session.flush()
        await self.session.refresh(atendimento)
        return atendimento

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
        self, tenant_id: int, status: AtendimentoStatus | None = None
    ) -> list[Atendimento]:
        query = select(Atendimento).where(Atendimento.tenant_id == tenant_id)
        if status:
            query = query.where(Atendimento.status == status)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def iniciar_conversa(
        self, instancia_id: int, tenant_id: int, numero: str, mensagem_inicial: str | None = None
    ) -> tuple["Atendimento", "MensagemAtendimento | None"]:
        """Cria um novo atendimento (ou retoma existente) iniciado pelo operador."""
        result = await self.session.execute(
            select(Atendimento).where(
                Atendimento.instancia_id == instancia_id,
                Atendimento.numero == numero,
                Atendimento.status != AtendimentoStatus.ENCERRADO,
            )
        )
        atendimento = result.scalar_one_or_none()
        if not atendimento:
            atendimento = Atendimento(
                numero=numero,
                instancia_id=instancia_id,
                tenant_id=tenant_id,
                status=AtendimentoStatus.HUMANO,
            )
            self.session.add(atendimento)
            await self.session.flush()
            await self.session.refresh(atendimento)
        elif atendimento.status == AtendimentoStatus.ATIVO:
            atendimento = await self.assumir(atendimento)

        msg = None
        if mensagem_inicial:
            instancia = await self.session.get(WhatsappInstancia, instancia_id)
            if instancia:
                try:
                    await self.client.post(
                        f"/message/sendText/{instancia.instance_name}",
                        json={"number": numero, "text": mensagem_inicial},
                    )
                except Exception:
                    pass  # falha no envio não impede criação do atendimento
            msg = await self.salvar_mensagem(atendimento.id, MensagemOrigem.OPERADOR, mensagem_inicial)

        return atendimento, msg

    async def enviar_mensagem_operador(
        self, atendimento: Atendimento, conteudo: str
    ) -> MensagemAtendimento:
        if atendimento.status != AtendimentoStatus.HUMANO:
            raise HTTPException(
                status_code=400,
                detail="Só é possível enviar mensagem quando o atendimento está em modo HUMANO",
            )

        # Busca instance_name da instância vinculada
        instancia = await self.session.get(WhatsappInstancia, atendimento.instancia_id)
        if instancia:
            try:
                await self.client.post(
                    f"/message/sendText/{instancia.instance_name}",
                    json={"number": atendimento.numero, "text": conteudo},
                )
            except Exception:
                pass  # falha no envio não impede salvar a mensagem

        return await self.salvar_mensagem(atendimento.id, MensagemOrigem.OPERADOR, conteudo)


def get_atendimento_service(
    session: AsyncDBSession, client: EvolutionClientDep
) -> AtendimentoService:
    return AtendimentoService(session, client)


AtendimentoServiceDep = Annotated[AtendimentoService, Depends(get_atendimento_service)]
