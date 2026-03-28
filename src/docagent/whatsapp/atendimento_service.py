from typing import Annotated

import httpx
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.atendimento.models import (
    Atendimento,
    AtendimentoStatus,
    CanalAtendimento,
    MensagemAtendimento,
    MensagemOrigem,
)
from docagent.database import AsyncDBSession
from docagent.whatsapp.client import EvolutionClientDep
from docagent.whatsapp.models import WhatsappInstancia


class WhatsappAtendimentoService:
    """Operações de atendimento específicas do canal WhatsApp."""

    def __init__(self, session: AsyncSession, client: httpx.AsyncClient):
        self.session = session
        self.client = client

    async def listar(
        self, tenant_id: int, status: AtendimentoStatus | None = None
    ) -> list[Atendimento]:
        query = select(Atendimento).where(
            Atendimento.tenant_id == tenant_id,
            Atendimento.canal == CanalAtendimento.WHATSAPP,
        )
        if status:
            query = query.where(Atendimento.status == status)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def criar_ou_retomar(
        self, instancia_id: int, tenant_id: int, numero: str
    ) -> Atendimento:
        """Busca atendimento WhatsApp ativo/humano para o número. Se não existe, cria novo."""
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
            canal=CanalAtendimento.WHATSAPP,
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

    async def iniciar_conversa(
        self, instancia_id: int, tenant_id: int, numero: str, mensagem_inicial: str | None = None
    ) -> tuple[Atendimento, MensagemAtendimento | None]:
        """Cria um novo atendimento WhatsApp (ou retoma existente) iniciado pelo operador."""
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
                canal=CanalAtendimento.WHATSAPP,
                tenant_id=tenant_id,
                status=AtendimentoStatus.HUMANO,
            )
            self.session.add(atendimento)
            await self.session.flush()
            await self.session.refresh(atendimento)
        elif atendimento.status == AtendimentoStatus.ATIVO:
            atendimento.status = AtendimentoStatus.HUMANO
            await self.session.flush()
            await self.session.refresh(atendimento)

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
                    pass
            msg = await self.salvar_mensagem(atendimento.id, MensagemOrigem.OPERADOR, mensagem_inicial)

        return atendimento, msg

    async def enviar_mensagem_operador(
        self, atendimento: Atendimento, conteudo: str
    ) -> MensagemAtendimento:
        """Envia mensagem do operador via Evolution API e salva no banco."""
        if atendimento.status != AtendimentoStatus.HUMANO:
            raise HTTPException(
                status_code=400,
                detail="Só é possível enviar mensagem quando o atendimento está em modo HUMANO",
            )
        instancia = await self.session.get(WhatsappInstancia, atendimento.instancia_id)
        if instancia:
            try:
                await self.client.post(
                    f"/message/sendText/{instancia.instance_name}",
                    json={"number": atendimento.numero, "text": conteudo},
                )
            except Exception:
                pass
        return await self.salvar_mensagem(atendimento.id, MensagemOrigem.OPERADOR, conteudo)


def get_whatsapp_atendimento_service(
    session: AsyncDBSession, client: EvolutionClientDep
) -> WhatsappAtendimentoService:
    return WhatsappAtendimentoService(session, client)


WhatsappAtendimentoServiceDep = Annotated[
    WhatsappAtendimentoService, Depends(get_whatsapp_atendimento_service)
]
