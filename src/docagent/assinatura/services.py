from datetime import datetime, timedelta
from typing import Annotated

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.agente.models import Agente, Documento
from docagent.assinatura.models import Assinatura
from docagent.database import AsyncDBSession


class AssinaturaService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> list[Assinatura]:
        result = await self.session.execute(select(Assinatura).order_by(Assinatura.id))
        return list(result.scalars().all())

    async def get_by_tenant(self, tenant_id: int) -> Assinatura | None:
        result = await self.session.execute(
            select(Assinatura).where(Assinatura.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def criar(self, tenant_id: int, plano_id: int) -> Assinatura:
        assinatura = await self.get_by_tenant(tenant_id)
        if assinatura:
            assinatura.plano_id = plano_id
            await self.session.flush()
            await self.session.refresh(assinatura)
            return assinatura

        from docagent.plano.models import Plano
        plano = await self.session.get(Plano, plano_id)
        agora = datetime.utcnow()
        assinatura = Assinatura(
            tenant_id=tenant_id,
            plano_id=plano_id,
            ativo=True,
            data_inicio=agora,
            data_proxima_renovacao=agora + timedelta(days=plano.ciclo_dias),
        )
        self.session.add(assinatura)
        await self.session.flush()
        await self.session.refresh(assinatura)
        return assinatura

    async def checar_quota(self, tenant_id: int, recurso: str) -> bool:
        """Retorna True se o tenant ainda está dentro do limite para o recurso."""
        assinatura = await self.get_by_tenant(tenant_id)
        if not assinatura or not assinatura.ativo:
            return True  # sem assinatura = acesso livre (demo)

        plano = assinatura.plano

        if recurso == "agentes":
            atual = await self._contar_agentes(tenant_id)
            return atual < plano.limite_agentes

        if recurso == "documentos":
            atual = await self._contar_documentos(tenant_id)
            return atual < plano.limite_documentos

        return True

    async def uso_atual(self, tenant_id: int) -> dict:
        assinatura = await self.get_by_tenant(tenant_id)
        agentes_atual = await self._contar_agentes(tenant_id)
        documentos_atual = await self._contar_documentos(tenant_id)

        if not assinatura:
            return {
                "plano": None,
                "agentes_atual": agentes_atual,
                "agentes_limite": None,
                "documentos_atual": documentos_atual,
                "documentos_limite": None,
            }

        plano = assinatura.plano
        return {
            "plano": plano.nome,
            "agentes_atual": agentes_atual,
            "agentes_limite": plano.limite_agentes,
            "documentos_atual": documentos_atual,
            "documentos_limite": plano.limite_documentos,
        }

    async def _contar_agentes(self, tenant_id: int) -> int:
        result = await self.session.execute(
            select(func.count(Agente.id)).where(Agente.tenant_id == tenant_id)
        )
        return result.scalar_one()

    async def _contar_documentos(self, tenant_id: int) -> int:
        result = await self.session.execute(
            select(func.count(Documento.id))
            .join(Agente, Documento.agente_id == Agente.id)
            .where(Agente.tenant_id == tenant_id)
        )
        return result.scalar_one()


def get_assinatura_service(session: AsyncDBSession) -> AssinaturaService:
    return AssinaturaService(session)


AssinaturaServiceDep = Annotated[AssinaturaService, Depends(get_assinatura_service)]
