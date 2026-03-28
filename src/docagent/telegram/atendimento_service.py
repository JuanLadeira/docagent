from typing import Annotated

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
from docagent.telegram.client import get_telegram_client
from docagent.telegram.models import TelegramInstancia


class TelegramAtendimentoService:
    """Operações de atendimento específicas do canal Telegram."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def listar(
        self, tenant_id: int, status: AtendimentoStatus | None = None
    ) -> list[Atendimento]:
        query = select(Atendimento).where(
            Atendimento.tenant_id == tenant_id,
            Atendimento.canal == CanalAtendimento.TELEGRAM,
        )
        if status:
            query = query.where(Atendimento.status == status)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def criar_ou_retomar(
        self, telegram_instancia_id: int, tenant_id: int, numero: str, nome_contato: str | None = None
    ) -> Atendimento:
        """Busca atendimento Telegram ativo/humano para o número. Se não existe, cria novo."""
        result = await self.session.execute(
            select(Atendimento).where(
                Atendimento.telegram_instancia_id == telegram_instancia_id,
                Atendimento.numero == numero,
                Atendimento.status != AtendimentoStatus.ENCERRADO,
            )
        )
        atendimento = result.scalar_one_or_none()
        if atendimento:
            return atendimento

        atendimento = Atendimento(
            numero=numero,
            nome_contato=nome_contato,
            canal=CanalAtendimento.TELEGRAM,
            telegram_instancia_id=telegram_instancia_id,
            instancia_id=None,
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

    async def enviar_mensagem_operador(
        self, atendimento: Atendimento, conteudo: str
    ) -> MensagemAtendimento:
        """Envia mensagem do operador via Telegram Bot API e salva no banco."""
        if atendimento.status != AtendimentoStatus.HUMANO:
            raise HTTPException(
                status_code=400,
                detail="Só é possível enviar mensagem quando o atendimento está em modo HUMANO",
            )
        if atendimento.telegram_instancia_id:
            tg = await self.session.get(TelegramInstancia, atendimento.telegram_instancia_id)
            if tg:
                try:
                    chat_id = int(atendimento.numero)
                    async with get_telegram_client(tg.bot_token) as client:
                        await client.post("/sendMessage", json={"chat_id": chat_id, "text": conteudo})
                except Exception:
                    pass
        return await self.salvar_mensagem(atendimento.id, MensagemOrigem.OPERADOR, conteudo)


def get_telegram_atendimento_service(session: AsyncDBSession) -> TelegramAtendimentoService:
    return TelegramAtendimentoService(session)


TelegramAtendimentoServiceDep = Annotated[
    TelegramAtendimentoService, Depends(get_telegram_atendimento_service)
]
