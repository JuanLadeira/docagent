"""
Dependencias FastAPI compartilhadas.
"""
from fastapi import Depends, HTTPException

from docagent.chat.session import InMemorySessionManager
from docagent.rag.ingest_service import IngestService
from docagent.auth.current_user import CurrentUser
from docagent.assinatura.services import AssinaturaServiceDep

# Singleton do session manager — substituído por RedisSessionManager no lifespan
# de api.py se REDIS_URL estiver configurada.
_session_manager: InMemorySessionManager = InMemorySessionManager()


def get_session_manager():
    return _session_manager


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
