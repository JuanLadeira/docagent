"""
Rate limiting centralizado — Fase 21a.

Instância única do Limiter compartilhada por todos os routers.
Por padrão usa memória local (worker único). Para múltiplas réplicas,
configure REDIS_URL e o storage_uri será usado automaticamente.
"""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from docagent.settings import Settings

_settings = Settings()

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_settings.REDIS_URL or "memory://",
)


def get_tenant_key(request: Request) -> str:
    """
    Chave de rate limit por tenant — usada no /chat para limitar custo de LLM.
    Extrai tenant_id do JWT sem validação completa (apenas leitura do payload).
    Cai para IP se o token estiver ausente/inválido.
    """
    import jwt as pyjwt

    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.removeprefix("Bearer ")
        try:
            payload = pyjwt.decode(token, options={"verify_signature": False})
            tenant_id = payload.get("tenant_id")
            if tenant_id:
                return f"tenant:{tenant_id}"
        except Exception:
            pass
    return get_remote_address(request)
