"""
Dependencias FastAPI compartilhadas.
"""
from functools import lru_cache

from fastapi import Depends, HTTPException

from docagent.chat.session import SessionManager
from docagent.rag.ingest_service import IngestService
from docagent.auth.current_user import CurrentUser
from docagent.assinatura.services import AssinaturaServiceDep


@lru_cache(maxsize=1)
def get_session_manager() -> SessionManager:
    return SessionManager()


def get_ingest_service() -> IngestService:
    return IngestService()


def require_quota(recurso: str):
    """
    FastAPI dependency factory que levanta HTTP 402 se quota excedida.

    Uso: Depends(require_quota("agentes"))
    """
    async def _check(
        current_user: CurrentUser,
        assinatura_service: AssinaturaServiceDep,
    ) -> None:
        ok = await assinatura_service.checar_quota(current_user.tenant_id, recurso)
        if not ok:
            raise HTTPException(
                status_code=402,
                detail=f"Limite de {recurso} atingido para o seu plano atual.",
            )

    return Depends(_check)
