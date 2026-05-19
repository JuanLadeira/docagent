import uuid

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from docagent.auth.security import create_access_token
from docagent.database import AsyncDBSession
from docagent.keycloak.service import KeycloakService, get_keycloak_client
from docagent.settings import Settings

router = APIRouter(prefix="/auth/keycloak", tags=["Keycloak SSO"])
config_router = APIRouter(tags=["Config"])


def _get_app_redis(request: Request):
    return getattr(request.app.state, "redis", None)


@router.get("/login")
async def keycloak_login(request: Request):
    kc = get_keycloak_client()
    if not kc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SSO Keycloak não configurado")

    state = str(uuid.uuid4())
    redis = _get_app_redis(request)
    if redis:
        await redis.set(f"keycloak:state:{state}", b"1", ex=300)

    s = Settings()
    url = kc.get_authorization_url(redirect_uri=s.KEYCLOAK_REDIRECT_URI, state=state)
    return RedirectResponse(url=url)


@router.get("/callback")
async def keycloak_callback(
    request: Request,
    code: str,
    state: str,
    db: AsyncDBSession,
):
    kc = get_keycloak_client()
    if not kc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SSO Keycloak não configurado")

    redis = _get_app_redis(request)

    if redis:
        state_key = f"keycloak:state:{state}"
        exists = await redis.get(state_key)
        if not exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="state inválido ou expirado")
        await redis.delete(state_key)

    s = Settings()
    try:
        tokens = await kc.exchange_code(code=code, redirect_uri=s.KEYCLOAK_REDIRECT_URI)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Falha ao trocar code Keycloak")

    try:
        claims = kc.validate_jwt(tokens["access_token"])
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="JWT Keycloak inválido")

    if not claims.get("email"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="JWT Keycloak sem claim 'email'")

    user = await KeycloakService.criar_ou_linkar_usuario(
        claims=claims,
        refresh_token=tokens["refresh_token"],
        db=db,
        redis=redis,
    )

    access_token = create_access_token(data={"sub": user.username})
    frontend_url = s.FRONTEND_URL
    return RedirectResponse(url=f"{frontend_url}/auth/callback?token={access_token}")


@config_router.get("/api/config/public")
async def config_public():
    s = Settings()
    enabled = bool(s.KEYCLOAK_URL)
    return {
        "keycloak_enabled": enabled,
        "keycloak_url": s.KEYCLOAK_URL if enabled else "",
        "keycloak_realm": s.KEYCLOAK_REALM if enabled else "",
        "keycloak_client_id": s.KEYCLOAK_CLIENT_ID if enabled else "",
    }
