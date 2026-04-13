from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.database import AsyncDBSession
from docagent.telegram.client import get_telegram_client
from docagent.telegram.models import TelegramBotStatus, TelegramInstancia
from docagent.telegram.schemas import TelegramInstanciaCreate, TelegramInstanciaUpdate


class TelegramService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def criar_instancia(
        self,
        tenant_id: int,
        data: TelegramInstanciaCreate,
        webhook_url: str,
    ) -> TelegramInstancia:
        instancia = TelegramInstancia(
            bot_token=data.bot_token,
            status=TelegramBotStatus.ATIVA,
            cria_atendimentos=data.cria_atendimentos,
            tenant_id=tenant_id,
            agente_id=data.agente_id,
        )
        self.session.add(instancia)
        await self.session.flush()

        async with get_telegram_client(data.bot_token) as client:
            # Registrar webhook
            await client.post("/setWebhook", json={"url": webhook_url})

            # Buscar username do bot
            resp = await client.post("/getMe")
            bot_info = resp.json()
            if bot_info.get("ok"):
                instancia.bot_username = bot_info["result"].get("username")

        instancia.webhook_configured = True
        await self.session.flush()
        await self.session.refresh(instancia)
        return instancia

    async def listar_instancias(self, tenant_id: int) -> list[TelegramInstancia]:
        result = await self.session.execute(
            select(TelegramInstancia)
            .where(TelegramInstancia.tenant_id == tenant_id)
            .order_by(TelegramInstancia.id)
        )
        return list(result.scalars().all())

    async def obter_instancia(
        self, instancia_id: int, tenant_id: int
    ) -> TelegramInstancia | None:
        result = await self.session.execute(
            select(TelegramInstancia).where(
                TelegramInstancia.id == instancia_id,
                TelegramInstancia.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def atualizar_instancia(self, instancia: TelegramInstancia, data: TelegramInstanciaUpdate) -> TelegramInstancia:
        instancia.agente_id = data.agente_id
        await self.session.flush()
        await self.session.refresh(instancia)
        return instancia

    async def deletar_instancia(self, instancia: TelegramInstancia) -> None:
        # Best-effort: cancela webhook antes de remover
        try:
            async with get_telegram_client(instancia.bot_token) as client:
                await client.post("/deleteWebhook")
        except Exception:
            pass
        await self.session.delete(instancia)
        await self.session.flush()

    async def configurar_webhook(
        self, instancia: TelegramInstancia, webhook_url: str
    ) -> TelegramInstancia:
        import secrets as _secrets
        webhook_secret = _secrets.token_hex(32)
        async with get_telegram_client(instancia.bot_token) as client:
            await client.post(
                "/setWebhook",
                json={"url": webhook_url, "secret_token": webhook_secret},
            )
        instancia.webhook_configured = True
        instancia.webhook_secret = webhook_secret
        await self.session.flush()
        await self.session.refresh(instancia)
        return instancia

    async def enviar_texto(
        self, instancia: TelegramInstancia, chat_id: int, text: str
    ) -> None:
        async with get_telegram_client(instancia.bot_token) as client:
            await client.post("/sendMessage", json={"chat_id": chat_id, "text": text})


def get_telegram_service(session: AsyncDBSession) -> TelegramService:
    return TelegramService(session)


TelegramServiceDep = Annotated[TelegramService, Depends(get_telegram_service)]
