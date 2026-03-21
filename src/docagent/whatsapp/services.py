from typing import Annotated

import httpx
from fastapi import Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.database import AsyncDBSession
from docagent.whatsapp.client import EvolutionClientDep
from docagent.whatsapp.models import ConexaoStatus, WhatsappInstancia
from docagent.whatsapp.schemas import (
    InstanciaCreate,
    InstanciaResumoStatus,
    MensagemMidiaRequest,
    MensagemTextoRequest,
)


class WhatsappService:
    def __init__(self, client: httpx.AsyncClient, session: AsyncSession):
        self.client = client
        self.session = session

    # ── Instâncias (DB + Evolution API) ─────────────────────────────

    async def criar_instancia(self, tenant_id: int, data: InstanciaCreate, webhook_url: str) -> WhatsappInstancia:
        # v1: webhook é string (URL), opções de webhook são campos separados
        r = await self.client.post(
            "/instance/create",
            json={
                "instanceName": data.instance_name,
                "qrcode": True,
                "webhook": webhook_url,
                "webhookByEvents": False,
                "webhookBase64": True,
                "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE", "QRCODE_UPDATED"],
            },
        )
        _verificar_resposta(r)

        instancia = WhatsappInstancia(
            instance_name=data.instance_name,
            tenant_id=tenant_id,
            agente_id=data.agente_id,
            status=ConexaoStatus.CRIADA,
        )
        self.session.add(instancia)
        await self.session.flush()
        await self.session.refresh(instancia)
        return instancia

    async def listar_instancias(self, tenant_id: int) -> list[WhatsappInstancia]:
        result = await self.session.execute(
            select(WhatsappInstancia).where(WhatsappInstancia.tenant_id == tenant_id)
        )
        return list(result.scalars().all())

    async def obter_instancia(self, instancia_id: int, tenant_id: int) -> WhatsappInstancia | None:
        result = await self.session.execute(
            select(WhatsappInstancia).where(
                WhatsappInstancia.id == instancia_id,
                WhatsappInstancia.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def obter_qrcode(self, instancia: WhatsappInstancia) -> dict:
        r = await self.client.get(f"/instance/connect/{instancia.instance_name}")
        _verificar_resposta(r)
        instancia.status = ConexaoStatus.CONECTANDO
        await self.session.flush()
        data = r.json()
        # Evolution API v2 retorna base64 em campos distintos dependendo do estado
        base64 = (
            data.get("base64")
            or data.get("qrcode", {}).get("base64")
            or data.get("code")
            or ""
        )
        if base64 and not base64.startswith("data:"):
            base64 = f"data:image/png;base64,{base64}"
        return {"base64": base64, "status": "CONECTANDO"}

    async def sincronizar_status(self, instancia: WhatsappInstancia) -> WhatsappInstancia:
        r = await self.client.get(f"/instance/connectionState/{instancia.instance_name}")
        _verificar_resposta(r)
        state = r.json().get("state", "")
        instancia.status = {
            "open": ConexaoStatus.CONECTADA,
            "connecting": ConexaoStatus.CONECTANDO,
            "close": ConexaoStatus.DESCONECTADA,
        }.get(state, ConexaoStatus.DESCONECTADA)
        await self.session.flush()
        await self.session.refresh(instancia)
        return instancia

    async def deletar_instancia(self, instancia: WhatsappInstancia) -> None:
        try:
            r = await self.client.delete(f"/instance/delete/{instancia.instance_name}")
            r.raise_for_status()
        except Exception:
            pass
        await self.session.delete(instancia)

    # ── Admin ────────────────────────────────────────────────────────

    async def listar_todas_instancias(self) -> list[WhatsappInstancia]:
        result = await self.session.execute(select(WhatsappInstancia))
        return list(result.scalars().all())

    async def resumo_status(self) -> InstanciaResumoStatus:
        result = await self.session.execute(
            select(WhatsappInstancia.status, func.count().label("qtd")).group_by(
                WhatsappInstancia.status
            )
        )
        contagens = {row.status: row.qtd for row in result}
        total = sum(contagens.values())
        return InstanciaResumoStatus(
            total=total,
            criadas=contagens.get(ConexaoStatus.CRIADA, 0),
            conectando=contagens.get(ConexaoStatus.CONECTANDO, 0),
            conectadas=contagens.get(ConexaoStatus.CONECTADA, 0),
            desconectadas=contagens.get(ConexaoStatus.DESCONECTADA, 0),
        )

    # ── Mensagens ────────────────────────────────────────────────────

    async def enviar_texto(self, instancia: WhatsappInstancia, data: MensagemTextoRequest) -> dict:
        r = await self.client.post(
            f"/message/sendText/{instancia.instance_name}", json=data.model_dump()
        )
        _verificar_resposta(r)
        return r.json()

    async def enviar_midia(self, instancia: WhatsappInstancia, data: MensagemMidiaRequest) -> dict:
        r = await self.client.post(
            f"/message/sendMedia/{instancia.instance_name}",
            json=data.model_dump(exclude_none=True),
        )
        _verificar_resposta(r)
        return r.json()


def _verificar_resposta(response: httpx.Response) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Evolution API error {e.response.status_code}: {e.response.text[:200]}",
        )


def get_whatsapp_service(client: EvolutionClientDep, session: AsyncDBSession) -> WhatsappService:
    return WhatsappService(client, session)


WhatsappServiceDep = Annotated[WhatsappService, Depends(get_whatsapp_service)]
