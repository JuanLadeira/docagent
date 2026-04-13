"""
AuditService — registra ações no audit_log.

Design intencional:
- registrar() nunca lança exceção — erros de audit não devem cancelar a operação principal.
- Não faz commit próprio — deixa o commit da operação principal levar junto.
- Se precisar registrar fora de uma transação ativa, usar registrar_e_commit().
"""
import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.audit.models import ActorTipo, AuditLog

_log = logging.getLogger(__name__)


class AuditService:

    @staticmethod
    async def registrar(
        db: AsyncSession,
        actor_tipo: ActorTipo,
        actor_id: int,
        actor_username: str,
        acao: str,
        tenant_id: int | None = None,
        recurso_tipo: str | None = None,
        recurso_id: int | None = None,
        dados_antes: dict | None = None,
        dados_depois: dict | None = None,
        ip_origem: str | None = None,
    ) -> None:
        """
        Adiciona um registro ao audit_log na sessão atual.
        Não faz commit — o commit da operação principal leva junto.
        Nunca lança exceção.
        """
        try:
            log = AuditLog(
                actor_tipo=actor_tipo,
                actor_id=actor_id,
                actor_username=actor_username,
                acao=acao,
                tenant_id=tenant_id,
                recurso_tipo=recurso_tipo,
                recurso_id=recurso_id,
                dados_antes=dados_antes,
                dados_depois=dados_depois,
                ip_origem=ip_origem,
            )
            db.add(log)
        except Exception as exc:
            _log.error("AuditService.registrar falhou silenciosamente: %s", exc)

    @staticmethod
    async def listar(
        db: AsyncSession,
        actor_id: int | None = None,
        actor_tipo: ActorTipo | None = None,
        acao: str | None = None,
        recurso_tipo: str | None = None,
        tenant_id: int | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AuditLog], int]:
        """Retorna (itens, total) com filtros opcionais."""
        query = select(AuditLog)

        if actor_id is not None:
            query = query.where(AuditLog.actor_id == actor_id)
        if actor_tipo is not None:
            query = query.where(AuditLog.actor_tipo == actor_tipo)
        if acao is not None:
            query = query.where(AuditLog.acao == acao)
        if recurso_tipo is not None:
            query = query.where(AuditLog.recurso_tipo == recurso_tipo)
        if tenant_id is not None:
            query = query.where(AuditLog.tenant_id == tenant_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar_one()

        offset = (page - 1) * page_size
        items_result = await db.execute(
            query.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size)
        )
        items = list(items_result.scalars().all())

        return items, total
