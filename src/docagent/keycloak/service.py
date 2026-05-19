import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.settings import Settings
from docagent.usuario.models import Usuario, UsuarioRole

_REDIS_RT_PREFIX = "keycloak:rt:{}"
_REDIS_RT_TTL = 60 * 60 * 24 * 7  # 7 dias


def get_keycloak_client():
    from docagent.keycloak.client import KeycloakClient
    s = Settings()
    if not s.KEYCLOAK_URL:
        return None
    return KeycloakClient(
        url=s.KEYCLOAK_URL,
        realm=s.KEYCLOAK_REALM,
        client_id=s.KEYCLOAK_CLIENT_ID,
        client_secret=s.KEYCLOAK_CLIENT_SECRET,
    )


class KeycloakService:
    @staticmethod
    async def criar_ou_linkar_usuario(
        claims: dict,
        refresh_token: str,
        db: AsyncSession,
        redis,
    ) -> Usuario:
        sub = claims["sub"]
        email = claims.get("email")
        if not email:
            raise ValueError("JWT Keycloak sem claim 'email'")

        # 1. Busca por keycloak_sub
        result = await db.execute(select(Usuario).where(Usuario.keycloak_sub == sub))
        user = result.scalar_one_or_none()

        # 2. Busca por email
        if not user:
            result = await db.execute(select(Usuario).where(Usuario.email == email))
            user = result.scalar_one_or_none()

        # 3. Cria novo usuário
        if not user:
            s = Settings()
            name = claims.get("name") or email.split("@")[0]
            username = email.split("@")[0] + "_" + str(uuid.uuid4())[:8]
            user = Usuario(
                username=username,
                email=email,
                nome=name,
                password="!keycloak",
                role=UsuarioRole.MEMBER,
                tenant_id=s.KEYCLOAK_DEFAULT_TENANT_ID,
                keycloak_sub=sub,
            )
            db.add(user)
            await db.flush()
        else:
            user.keycloak_sub = sub
            await db.flush()

        if redis:
            key = _REDIS_RT_PREFIX.format(user.id)
            await redis.set(key, refresh_token, ex=_REDIS_RT_TTL)

        return user

    @staticmethod
    async def get_access_token(usuario_id: int, redis) -> str | None:
        if not redis:
            return None
        key = _REDIS_RT_PREFIX.format(usuario_id)
        rt = await redis.get(key)
        if not rt:
            return None
        rt_str = rt.decode() if isinstance(rt, bytes) else rt
        kc = get_keycloak_client()
        if not kc:
            return None
        try:
            tokens = await kc.refresh(rt_str)
            new_rt = tokens.get("refresh_token", rt_str)
            await redis.set(key, new_rt, ex=_REDIS_RT_TTL)
            return tokens["access_token"]
        except Exception:
            return None
